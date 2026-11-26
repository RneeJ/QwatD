import socket
import struct
import time

DR134_IP = "192.168.2.202"  # <-- Pas aan naar het IP-adres van je PUSR-DR134
DR134_PORT = 8899

def add_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return data + struct.pack("<H", crc)

def make_fc03_req(slave: int, start_addr: int, count: int) -> bytes:
    return add_crc(struct.pack(">BBHH", slave, 3, start_addr, count))

def make_fc03_resp(slave: int, values: list[int]) -> bytes:
    payload = struct.pack(">BBB", slave, 3, len(values) * 2)
    for v in values:
        payload += struct.pack(">h" if v < 0 else ">H", v)
    return add_crc(payload)

# Realistische Quatt testblokken (Request + bijbehorende Response)
frames = [
    # Blok 2099 (7 regs): Mode=2, AC_V=231, AC_A=42 (4.2A), Freq_dem=45, Freq_act=45, Fan_max=650, Fan_act=580
    (make_fc03_req(1, 2099, 7), make_fc03_resp(1, [2, 231, 42, 45, 45, 650, 580])),
    # Blok 2110 (3 regs): Outside=-2.5°C (-25), EvapCoil=-4.0°C (-40), Discharge=54.0°C (540)
    (make_fc03_req(1, 2110, 3), make_fc03_resp(1, [-25, -40, 540])),
    # Blok 2131 (4 regs): CondTemp=34.5°C (345), EvapTemp=-1.2°C (-12), WaterIn=28.4°C (284), WaterOut=33.1°C (331)
    (make_fc03_req(1, 2131, 4), make_fc03_resp(1, [345, -12, 284, 331])),
    # Blok 2137 (2 regs): PumpPower=38W, PumpFlow=185 (18.5 L/min)
    (make_fc03_req(1, 2137, 2), make_fc03_resp(1, [38, 185])),
]

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((DR134_IP, DR134_PORT))
print(f"Verbonden met simulator DR134 ({DR134_IP}:{DR134_PORT})...")

try:
    while True:
        for req, resp in frames:
            sock.sendall(req)
            time.sleep(0.05)   # Korte pauze tussen CiC-vraag en WP-antwoord
            sock.sendall(resp)
            time.sleep(0.08)   # Pauze tot volgende registerblok
        time.sleep(0.5)
except KeyboardInterrupt:
    sock.close()
