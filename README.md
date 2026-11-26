# QwatD
QwatD - A Quatt to Domoticz Modbus sniffer

There is an excellent [Quatt plugin for Domoticz](https://github.com/galadril/Domoticz-Quatt-Plugin), it is easy to install and the way to go ! 

WARNING : You need to know what you are doing because this solution connects to your heatpump on a hardware level !
You use it on your own risk.

Thankx for inspiration : [OpenQuatt](https://github.com/OpenQuatt/OpenQuatt) and [Quatt-sniffer](https://github.com/M10tech/Quatt-sniffer)

# Quatt Modbus Sniffer voor Domoticz (via USR-DR164 & Docker)

Een passieve (**100% read-only**) Modbus RTU-sniffer in Docker voor de **Quatt hybride warmtepomp** (zowel **Quatt Single** als **Quatt Duo**). De tool luistert mee op de RS485-verbinding tussen de Quatt CiC en de buitenunit(s) via een **PUSR USR-DR164** en publiceert alle meetwaarden als JSON naar MQTT voor directe uitlezing in **Domoticz** (via MQTTMapper).

## 1. Veiligheid & Hardware-aansluiting (Read-Only)

De Quatt CiC is de enige Modbus Master op de RS485-bus. Deze oplossing stuurt **nooit** bytes terug op de bus en vormt daarom geen enkel risico voor de werking van de warmtepomp.

1. **Spanning uitschakelen:** Schakel zowel de Quatt buitenunit(s) als de CiC volledig spanningsloos voordat je de kabel aansluit.
2. **Aftakkabel maken (Y-splitsing):**
   * Maak een korte aftakking (**< 0,5 tot 1 meter**) met getwiste aders (bijv. UTP Cat5e of LiYCY) vanaf de RS485-verbinding tussen CiC en buitenunit naar de USR-DR164.
   * Verbind **A op A**, **B op B** en **GND op GND** (bijv. met Wago 221-hendelklemmen).
   * Plaats **geen** extra 120 Ω afsluitweerstand op de aftakking (de bus is al afgesloten in de CiC en buitenunit).
3. **Voeding USR-DR164:** Gebruik een eigen 5V–24V DC adapter op de klemmenstrook van de DR164 zodat de CiC elektrisch niet wordt belast.

## 2. Instellingen op de USR-DR164

Configureer de USR-DR164 via de webinterface:
* **Netwerk:** Vast IP-adres (bijv. `192.168.2.181`), Socket A op **TCP Server**, poort `8899`.
* **Work Mode:** **Transparent Transmission** (*geen* Modbus Protocol Conversion inschakelen).
* **Seriële poort:** `9600 baud`, `8 databits`, `No parity`, `1 stopbit` (`9600 8N1`).

## 3. Docker-container starten

Zet `quatt_sniffer.py`, `Dockerfile`, `requirements.txt` en `docker-compose.yml` in een map (bijv. `~/quatt-sniffer`), pas in `docker-compose.yml` het IP-adres (`DR164_IP`) en `QUATT_UNITS` (`1` voor Single, `2` voor Duo) aan en start de container:

```bash
docker compose up -d --build
docker logs -f quatt-sniffer
```

### Eerste controle & schaalfactoren verifiëren
Zet in `docker-compose.yml` tijdelijk `RAW_LOG=true` om de ruwe Modbus-registers naast de berekende waarden in `docker logs` te zien en te vergelijken met de CiC (`http://<CIC-IP>:8080/beta/feed/data.json`). Zet `RAW_LOG=false` zodra alles klopt.

## 4. Domoticz koppelen (MQTTMapper)

1. Kopieer de inhoud van **`MqttMapper_Single.json`** (of **`MqttMapper_Duo.json`**) naar je `MqttMapper.json`-configuratiebestand.
2. Zet in Domoticz onder **Instellingen → Systeem** tijdelijk *Nieuwe hardware/apparaten toestaan* aan en herstart de MQTTMapper-hardware.
3. Alle sensoren (water aanvoer/retour, buitentemperatuur, flow, pompvermogen, compressorfrequentie, drukken, defrost- en klepstatussen) worden automatisch aangemaakt onder **Overige** en **Temperatuur**.
