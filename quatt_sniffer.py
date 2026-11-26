import os
import time
import json
import socket
import struct
import threading
import paho.mqtt.client as mqtt

# =============================================================================
# Configuratie via omgevingsvariabelen
# =============================================================================
DR164_IP = os.getenv("DR164_IP", "192.168.2.203")			# use a fixed IP adres
DR164_PORT = int(os.getenv("DR164_PORT", "8899"))
QUATT_UNITS = int(os.getenv("QUATT_UNITS", "1"))          # 1 = Single, 2 = Duo
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "Quatt").rstrip("/")
MQTT_USER = os.getenv("MQTT_USER", "****")			# Your MQTT credentials
MQTT_PASS = os.getenv("MQTT_PASS", "****")			# Your MQTT credentials

RAW_LOG = os.getenv("RAW_LOG", "false").lower() in ("1", "true", "yes")


# =============================================================================
# Modbus CRC-16 berekening & helperfuncties
# =============================================================================
def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 0x0001) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


def verify_crc(frame: bytes) -> bool:
    if len(frame) < 4:
        return False
    calc_crc = modbus_crc16(frame[:-2])
    recv_crc = struct.unpack("<H", frame[-2:])[0]
    return calc_crc == recv_crc


def to_signed16(val: int) -> int:
    return val - 0x10000 if val >= 0x8000 else val


# =============================================================================
# Quatt Register Decoder (gebaseerd op M10tech/Quatt-sniffer & CiC 4.2.0+)
# =============================================================================
class QuattDecoder:
    def __init__(self, max_units: int = 1):
        self.max_units = max_units
        self.lock = threading.Lock()
        # Bewaart per slave_id de laatst verzonden FC=03 aanvraag: (start_addr, count, timestamp)
        self.pending_requests = {}
        # Bewaart per slave_id de meest recente gedecodeerde sensordata
        self.unit_data = {
            unit_id: {"unit": f"hp{unit_id}", "slave_id": unit_id}
            for unit_id in range(1, max_units + 1)
        }

    def handle_frame(self, frame: bytes):
        slave_id = frame[0]
        fc = frame[1]

        if slave_id < 1 or slave_id > self.max_units:
            return

        with self.lock:
            # -----------------------------------------------------------------
            # FC=16 (0x10): Write Multiple Registers (CiC -> HP stuurcommando)
            # Request lengte: 11 bytes (bij 1 register: addr(1)+fc(1)+start(2)+cnt(2)+bc(1)+val(2)+crc(2))
            # Response lengte: 8 bytes
            # -----------------------------------------------------------------
            if fc == 0x10 and len(frame) >= 11:
                start_addr, reg_count = struct.unpack(">HH", frame[2:6])
                byte_count = frame[6]
                if len(frame) == 9 + byte_count and reg_count >= 1:
                    vals = [
                        struct.unpack(">H", frame[7 + i * 2 : 9 + i * 2])[0]
                        for i in range(reg_count)
                    ]
                    if RAW_LOG:
                        print(f"[HP{slave_id}][FC16] start={start_addr} vals={vals}", flush=True)
                    self._decode_registers(slave_id, start_addr, vals)

            # -----------------------------------------------------------------
            # FC=06 (0x06): Write Single Register (oudere CiC firmware)
            # -----------------------------------------------------------------
            elif fc == 0x06 and len(frame) == 8:
                start_addr, val = struct.unpack(">HH", frame[2:6])
                if RAW_LOG:
                    print(f"[HP{slave_id}][FC06] start={start_addr} val={val}", flush=True)
                self._decode_registers(slave_id, start_addr, [val])

            # -----------------------------------------------------------------
            # FC=03 (0x03): Read Holding Registers
            # Request van CiC is altijd 8 bytes; Response van HP is 5 + byte_count bytes
            # -----------------------------------------------------------------
            elif fc == 0x03:
                if len(frame) == 8:
                    start_addr, reg_count = struct.unpack(">HH", frame[2:6])
                    self.pending_requests[slave_id] = (start_addr, reg_count, time.time())
                elif len(frame) >= 5:
                    byte_count = frame[2]
                    if len(frame) == 5 + byte_count and byte_count % 2 == 0:
                        reg_count = byte_count // 2
                        req = self.pending_requests.pop(slave_id, None)
                        if req and (time.time() - req[2]) < 1.5 and req[1] == reg_count:
                            start_addr = req[0]
                            vals = [
                                struct.unpack(">H", frame[3 + i * 2 : 5 + i * 2])[0]
                                for i in range(reg_count)
                            ]
                            if RAW_LOG:
                                print(f"[HP{slave_id}][FC03] start={start_addr} cnt={reg_count} vals={vals}", flush=True)
                            self._decode_registers(slave_id, start_addr, vals)

    def _decode_registers(self, slave_id: int, start_addr: int, vals: list):
        data = self.unit_data[slave_id]

        for offset, raw in enumerate(vals):
            reg = start_addr + offset
            sval = to_signed16(raw)

            # --- Stuurregisters vanuit CiC ---
            if reg == 1999:
                data["compressor_level_demand"] = raw
            elif reg == 2006:
                data["silent_mode"] = raw
            elif reg == 2010:
                data["pump_mode_demand"] = raw
            elif reg == 2015:
                data["pump_level_demand"] = raw
            elif reg == 3999:
                data["working_mode_demand"] = raw

            # --- Status & Meetregisters van de Warmtepomp ---
            elif reg == 2099:
                data["working_mode_actual"] = raw
            elif reg == 2100:
                data["ac_voltage"] = raw
            elif reg == 2101:
                data["ac_current"] = round(raw * 0.1, 1)
            elif reg == 2102:
                data["compressor_freq_demand"] = raw
            elif reg == 2103:
                data["compressor_freq_actual"] = raw
            elif reg == 2104:
                data["fan_speed_max"] = raw
            elif reg == 2105:
                data["fan_speed_actual"] = raw
            elif reg == 2107:
                data["eev_steps"] = raw
            elif reg == 2108:
                data["status_2108"] = raw
                data["fan_low_speed"] = 1 if (raw & (1 << 0)) else 0
                data["bottom_heater"] = 1 if (raw & (1 << 2)) else 0
                data["crankcase_heater"] = 1 if (raw & (1 << 3)) else 0
                data["fan_defrost_speed"] = 1 if (raw & (1 << 4)) else 0
                data["fan_high_speed"] = 1 if (raw & (1 << 5)) else 0
                data["four_way_valve"] = 1 if (raw & (1 << 6)) else 0
                data["pump_relay"] = 1 if (raw & (1 << 11)) else 0

            # --- Temperaturen (let op: signed 16-bit voor vorst onder 0 °C) ---
            elif reg == 2110:
                data["temp_outside"] = round(sval * 0.1, 1)
            elif reg == 2111:
                data["temp_evaporator_coil"] = round(sval * 0.1, 1)
            elif reg == 2112:
                data["temp_gas_discharge"] = round(sval * 0.1, 1)
            elif reg == 2113:
                data["temp_gas_return"] = round(sval * 0.1, 1)

            # --- Drukken & Alarmbits ---
            elif reg == 2115:
                data["dipswitch"] = raw
            elif reg == 2116:
                data["pressure_evaporator"] = round(raw * 0.01, 2)
            elif reg == 2117:
                data["pressure_condenser"] = round(raw * 0.01, 2)
            elif reg == 2118:
                data["defrost_mode"] = 1 if (raw & (1 << 0)) else 0
            elif reg == 2119:
                data["alarm_2119"] = raw
            elif reg == 2120:
                data["alarm_2120"] = raw
            elif reg == 2121:
                data["alarm_2121"] = raw
            elif reg == 2122:
                data["firmware_version"] = raw
            elif reg == 2123:
                data["eeprom_version"] = raw

            # --- Water- en koudemiddeltemperaturen ---
            elif reg == 2131:
                data["temp_condensing"] = round(sval * 0.1, 1)
            elif reg == 2132:
                data["temp_evaporating"] = round(sval * 0.1, 1)
            elif reg == 2133:
                data["temp_water_in"] = round(sval * 0.1, 1)
            elif reg == 2134:
                data["temp_water_out"] = round(sval * 0.1, 1)
            elif reg == 2135:
                data["temp_condenser_coil"] = round(sval * 0.1, 1)

            # --- Pompvermogen en Waterflow ---
            elif reg == 2137:
                data["pump_power"] = raw
            elif reg == 2138:
                data["pump_flow"] = round(raw * 0.1, 1)

    def get_snapshot(self):
        with self.lock:
            return {
                unit_id: dict(payload)
                for unit_id, payload in self.unit_data.items()
                if len(payload) > 2
            }


# =============================================================================
# Stream-parser die Modbus RTU frames met geldige CRC uit de bytestream haalt
# =============================================================================
def extract_frames(buffer: bytearray, decoder: QuattDecoder):
    while len(buffer) >= 5:
        slave_id = buffer[0]
        fc = buffer[1]

        # Alleen bekende Quatt slave ID's (1 of 2) en ondersteunde FC's (3, 6, 16)
        if slave_id not in (1, 2) or fc not in (0x03, 0x06, 0x10):
            del buffer[0]
            continue

        possible_lengths = []
        if fc == 0x03:
            # Request is 8 bytes; Response is 5 + byte_count
            possible_lengths.append(8)
            if len(buffer) >= 3:
                bc = buffer[2]
                if 2 <= bc <= 120 and bc % 2 == 0:
                    possible_lengths.append(5 + bc)
        elif fc == 0x06:
            possible_lengths.append(8)
        elif fc == 0x10:
            # Response is 8 bytes; Request is 9 + byte_count
            possible_lengths.append(8)
            if len(buffer) >= 7:
                bc = buffer[6]
                if 2 <= bc <= 120 and bc % 2 == 0:
                    possible_lengths.append(9 + bc)

        matched = False
        for flen in sorted(set(possible_lengths)):
            if len(buffer) >= flen:
                candidate = bytes(buffer[:flen])
                if verify_crc(candidate):
                    decoder.handle_frame(candidate)
                    del buffer[:flen]
                    matched = True
                    break

        if not matched:
            # Wacht op meer bytes als de maximale kandidaat nog niet compleet is
            max_len = max(possible_lengths) if possible_lengths else 8
            if len(buffer) < max_len:
                break
            # Geen geldige CRC: schuif 1 byte op om opnieuw te synchroniseren
            del buffer[0]


# =============================================================================
# Hoofdprogramma: Read-Only TCP-client + periodieke MQTT-publisher
# =============================================================================
def mqtt_publisher_loop(mqtt_client: mqtt.Client, decoder: QuattDecoder):
    while True:
        time.sleep(PUBLISH_INTERVAL)
        snapshots = decoder.get_snapshot()
        for unit_id, payload in snapshots.items():
            topic = f"{MQTT_TOPIC_PREFIX}/hp{unit_id}"
            mqtt_client.publish(topic, json.dumps(payload))


def main():
    decoder = QuattDecoder(max_units=QUATT_UNITS)

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER:
        mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

    pub_thread = threading.Thread(
        target=mqtt_publisher_loop, args=(mqtt_client, decoder), daemon=True
    )
    pub_thread.start()

    print(
        f"Start Quatt Modbus Sniffer (units={QUATT_UNITS}, interval={PUBLISH_INTERVAL}s, raw_log={RAW_LOG}) "
        f"vanaf {DR164_IP}:{DR164_PORT} -> MQTT {MQTT_BROKER}:{MQTT_PORT} ({MQTT_TOPIC_PREFIX}/hpX)",
        flush=True,
    )

    rx_buffer = bytearray()

    while True:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((DR164_IP, DR164_PORT))
            print(f"Verbonden met USR-DR164 op {DR164_IP}:{DR164_PORT} (100% Read-Only)", flush=True)
            rx_buffer.clear()

            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    raise ConnectionError("Verbinding gesloten door USR-DR164")
                rx_buffer.extend(chunk)
                extract_frames(rx_buffer, decoder)
                # Voorkom geheugengroei bij ruis op de lijn
                if len(rx_buffer) > 4096:
                    del rx_buffer[:-256]

        except Exception as e:
            print(f"Verbindingsmelding ({DR164_IP}:{DR164_PORT}): {e} — opnieuw verbinden over 5s...", flush=True)
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            time.sleep(5)


if __name__ == "__main__":
    main()
