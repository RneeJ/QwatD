`Status : tested but not live`

# QwatD : Quatt Modbus Sniffer for Domoticz using USR-DR164 & Docker
A passive (**read-only**) Modbus RTU sniffer running in Docker for the **Quatt hybrid heat pump** (both **Quatt Single** and **Quatt Duo** models). The tool monitors the RS485 connection between the Quatt CiC and the outdoor unit(s) via a **PUSR USR-DR164** device, publishing all measured values ​​as JSON to MQTT for direct integration into **Domoticz** (using MqttMapper).

[Short : the DR164 delivers Quatt data hassle free on your servers doorstep where this tool translates it to usable json and send it out by MQTT.](/hints/hints.md#how-the-passive-modbus-sniffer-works-as-of-november-2026)

For mainstream use there is an excellent [Quatt plugin for Domoticz](https://github.com/galadril/Domoticz-Quatt-Plugin), it is easy to install and the way to go ! 

**WARNING : You need to know what you are doing because this solution connects to your heatpump on a hardware level !
You use it on your own risk.**

Intended users : Advanced

Thankx for inspiration : [OpenQuatt](https://github.com/OpenQuatt/OpenQuatt) and [Quatt-sniffer](https://github.com/M10tech/Quatt-sniffer) and Google AI.

# Prerequisites (install software if not present, buy DR164) :
- [Docker](https://www.docker.com/) preferred for all
- [Mosquito](https://mosquitto.org/)
- Optional [MQTT Explorer](https://mqtt-explorer.com/)
- [Domoticz](https://www.domoticz.com/)
- plugin for Domoticz [MqttMapper](https://github.com/FlyingDomotic/domoticz-mqttmapper-plugin)
- [PUSR USR-DR164](https://www.pusr.com/products/Serial-to-Dual-Band-WiFi-Converter.html)

# Steps to go after installed prerequisites :

## 1. Settings on the USR-DR164 
Read the manual and configure the USR-DR164 via its web interface:
* **Network:** Static IP address (e.g., `192.168.2.203`), Socket A set to **TCP Server**, port `8899`.
* **Work Mode:** **Transparent Transmission** (do *not* enable Modbus Protocol Conversion).
* **Serial Port:** `9600 baud`, `8 data bits`, `No parity`, `1 stop bit` (`9600 8N1`).

[Hints for setup](/hints/hints.md#1-usr-dr164)

## 2. Safety & Hardware Connection (Read-Only)
The Quatt CiC acts as the sole Modbus Master on the RS485 bus. This solution does not transmit onto the bus, ensuring there is absolutely no risk to the operation of the heat pump.

1. **Power Down:** Completely disconnect power to both the Quatt outdoor unit(s) and the CiC before connecting any cables ! 
2. **Create a Branch (Y-split):**
   * Create a short branch connection (**< 0.5 to 1 meter**) using twisted-pair wiring (e.g., UTP Cat5e or LiYCY) from the RS485 line (between the CiC and the outdoor unit) to the USR-DR164.
   * Connect **A to A**, **B to B**, and **GND to GND** (for example, using Wago 221 lever-operated connectors).
   * Do **not** add an extra 120 Ω termination resistor to this branch (the bus is already terminated within the CiC and the outdoor unit).
3. **Powering the USR-DR164:** Use a separate 5V–24V DC power adaptor connected to the DR164’s terminal block to ensure no electrical load is placed on the CiC.

[Hints for setup](/hints/hints.md#2-connecting-to-the-cic)

## 3. Starting the Docker container
Place `quatt_sniffer.py`, `Dockerfile`, `requirements.txt`, and `docker-compose.yml` into a directory (e.g., `~/quatt-sniffer`). 
In `docker-compose.yml`, adjust the IP address (`DR164_IP`) and `QUATT_UNITS` (`1` for Single, `2` for Duo), then start the container:

```bash
docker compose up -d --build
docker logs -f quatt-sniffer
```
### Initial check & verifying scaling factors
Temporarily set `RAW_LOG=true` in `docker-compose.yml` to view the raw Modbus registers alongside the calculated values ​​in the `docker logs`. Compare these with the data from the CiC (`http://<CIC-IP>:8080/beta/feed/data.json`). Once everything is correct, set `RAW_LOG=false`.

[Hints for setup](/hints/hints.md#3-the-docker-container)

## 4. Connecting to Domoticz (MQTTMapper)

1. Copy the contents of **`MqttMapper_Single.json`** (or **`MqttMapper_Duo.json`**) into your `MqttMapper.json` configuration file.
2. In Domoticz, go to **Settings → System** and temporarily enable *Allow new hardware/devices*, then restart the MQTTMapper hardware.
3. All sensors (water supply/return, outdoor temperature, flow, pump power, compressor frequency, pressures, defrost and valve statuses) will be created automatically under **Other** and **Temperature**.

[Hints for setup](/hints/hints.md#4-mqttmapper)

# Testing
Testing was done by using a connected Pusr-DR134 to send a dummy Quatt message from an included `simulate_quatt.py`.
You can run this locally on your pc. (use : Visual Studio Code)

[Hints for setup](/hints/hints.md#testing)
