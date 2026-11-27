# Hits for setup

## How the passive Modbus sniffer works (as of November 2026):
Since the USR-DR164 operates in "Transparent Transmission" mode, bytes from the RS485 bus arrive via TCP as a continuous data stream. The bus carries alternating requests (from the CiC to HP1/HP2) and responses (from HP1/HP2 back to the CiC):
Frame recognition via CRC-16: The parser scans the incoming byte stream for valid Modbus RTU frames with a correct CRC-16 checksum (this ensures packets never go out of sync, even if two frames arrive concatenated).

Linking requests to responses:
 - FC=16 (Write Multiple Registers, 11 bytes long): Contains direct control commands from the CiC (1999, 2006, 2010, 2015, 3999) intended for Slave 1 or 2. The sniffer can read these directly.
 - FC=03 Request (8 bytes long): The CiC requests N registers starting from address X (e.g., 2099, 2107, 2110, 2115, 2131, 2137) from Slave 1 or 2. The sniffer stores this information (slave_id, start_addr, reg_count).
 - FC=03 Response (5 + 2*N bytes long): The direct response from the corresponding slave, containing the N register values. The sniffer associates this with the previously stored start address and updates the corresponding values.
 - Throttled MQTT publication: The CiC polls 7 blocks every second. To avoid overwhelming Domoticz and the MQTT broker with 14 individual messages per second, the sniffer bundles all values ​​for each unit and publishes a single, complete JSON message per heat pump (HP) every 5 seconds (configurable via `PUBLISH_INTERVAL`).
 - Raw Debug mode (`RAW_LOG=true`): A built-in logging option that allows for the immediate inspection of raw decimal/hexadecimal values ​​upon initial connection, making it possible to verify the exact scaling factors (e.g., × 0.1 or × 0.01). Compare the to your Quatt API values and adjust if necessary.


| Registers	                  | number	         |About|
| ----------------------------|------------------| --------------------------------------------------------------------------- |
| 1999, 2006, 2010, 2015, 3999|	5× 1 reg (FC=16)|	Control from CiC: operating mode, compressor level, pump level, silent mode|
| 2099 to 2105|	7 reg (FC=03)|	Actual mode, compressor AC voltage & current, frequency, fan speed|
| 2107 to 2108|	2 reg (FC=03)|	Expansion valve, heaters, 4-way valve, pump relay|
| 2110 to 2112|	3 reg (FC=03)|	Outdoor temperature, evaporator and discharge gas temperature|
| 2115 to 2123|	9 reg (FC=03)|	Evaporator/condenser pressure, defrost mode, alarm/status bits|
| 2131 to 2134|	4 reg (FC=03)|	Condensing/evaporating temperature, water inlet & water outlet temperature|
| 2137 to 2138|	2 reg (FC=03)|	Pump power & water flow|


## 1. USR-DR164 
You can buy the PUSR USR-164 at the PUSR store at Alie. You need the **RS485** lipstick.

IMPORTANT : be carefull with setting up the DR164. If you used it before use the "reload" function at the left side to erase old settings.
Only one wrong setting can end up failing the process to work.

<img width="188" height="134" alt="QwatD - DR164 Work mode" src="https://github.com/user-attachments/assets/bb882ea7-19e9-4775-982e-546f126e0f2d" />
<img width="188" height="134" alt="QwatD - DR164 Sta Setting" src="https://github.com/user-attachments/assets/0c8ef484-44db-429a-9566-70434dfb182e" />
<img width="188" height="134" alt="QwatD - DR164 Serial Setting" src="https://github.com/user-attachments/assets/b6cd9f41-61a8-40d0-9d71-4eba6ac5f853" />
<img width="188" height="134" alt="QwatD - DR164 Net Setting" src="https://github.com/user-attachments/assets/4d18950a-8880-47ef-9b39-025af6e5678e" />

## 2. Connecting to the CiC
1. **Power Down:** Let your heatpump come to a halt by lowering the temperature. The heatpump should be completly off and outside temperature should be well above zero to prevent frost. Completely disconnect power both the Quatt outdoor unit(s) and the CiC before connecting any cables ! 
2. **Connect cables:** A good option is to put cables together in a **ferrule** (adereindhuls)
3. **Powering the USR-DR164:** You can use any old 5 volt 0,5 A - 1,0 A household adapter. The DR-164 only needs 170–350 mA at 5V (roughly 0.85–1.75 W at 5V)

## 3. The Docker container
This easy setup only has to concentrate on decoding the messages over modbus, because the DR164 handles all the communication in and out.
It all resulted in a very short python program of about 300 lines and 14 kb, the complete python environment in the docker image however needs around 150 Mb. 

Advise : Use a tool like Portainer to manage your docker environment.

| Command | Description|
|--------------------------------|------------------------------------------------------------------------|
| `docker compose up -d --build` | Creates and runs the container from the descriptive files in the same directory | 
| `docker logs -f quatt-sniffer` | Gives info about the running status of the container|

## 4. MQTTMapper
As mentioned before the python sniffer program only handles decoding. For ease of use the fine **`MqttMapper ** plugin of Domoticz is used. It handles the conversion of the MQTT messages (in json format) into Domoticz devices. 

You can copy the lines from _Single or _Duo into your own `MqttMapper.json` configuration file in the `~/plugins/MqttMapper` directory of your Domoticz system.

When copying **(appending !) into an existing `MqttMapper.json` you have to remove the last } of the existing and the first { of the new lines, connect old and new by adding a ',' to the forelast } !**

MqttMapper only reads the configuration file at startup of Domoticz ; so every change needs a restart of Domoticz.

# Testing
When testing with an other RS485 device you need the same communication parameters on the RS485 side as on the DR164 side.
<img width="260" height="402 alt="QwatD - Test DR134 - DR164" src="https://github.com/user-attachments/assets/5c0815d3-fc8c-415d-a070-a74559c7ac2f" />
