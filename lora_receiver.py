#!/usr/bin/env python3
"""
LoRa Receiver - Prosty odbiornik i dekoder wszystkich pakietów LoRa
Tylko odbiera, dekoduje i wyświetla - NIE zapisuje do bazy
"""

import os
import paho.mqtt.client as mqtt
import json
import base64
from datetime import datetime

# ========== KONFIGURACJA BROKERA LoRa ==========
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = "application/bcb75d00-e41b-4f24-9891-2d26072205e2/device/ac1f09fffe19fc8a/event/up"

# ========== DEKODERY PAKIETÓW ==========

def decode_packet_0x01(payload_hex):
    """
    Packet 0x01: Power Module (co ~7 sekund)
    Format: 01 CCCC CCCC CCCC SSSS TTTT TTTT
    
    Przykład: 010CA40CBB0D0B0A460A78
    - 01 = typ pakietu
    - 0CA4 = Cell 1 voltage (3236 / 1000 = 3.236V)
    - 0CBB = Cell 2 voltage (3259 / 1000 = 3.259V)
    - 0D0B = Cell 3 voltage (3339 / 1000 = 3.339V)
    - 0A46 = Pack temp BMS (2630 / 100 = 26.30°C)
    - 0A78 = Pack temp Charger (2680 / 100 = 26.80°C)
    """
    if len(payload_hex) < 14:
        return None
    
    packet_type = payload_hex[0:2]
    if packet_type != "01":
        return None
    
    # Dekoduj napięcia cel (3 x 2 bajty)
    cell1_hex = payload_hex[2:6]
    cell2_hex = payload_hex[6:10]
    cell3_hex = payload_hex[10:14]
    
    cell1_voltage = int(cell1_hex, 16) / 1000.0
    cell2_voltage = int(cell2_hex, 16) / 1000.0
    cell3_voltage = int(cell3_hex, 16) / 1000.0
    
    result = {
        "packet_type": "0x01",
        "packet_name": "Power Module",
        "cell1_voltage": cell1_voltage,
        "cell2_voltage": cell2_voltage,
        "cell3_voltage": cell3_voltage
    }
    
    # Jeśli są dodatkowe dane (temperatury)
    if len(payload_hex) >= 22:
        temp_bms_hex = payload_hex[14:18]
        temp_charger_hex = payload_hex[18:22]
        
        result["pack_temp_bms"] = int(temp_bms_hex, 16) / 100.0
        result["pack_temp_charger"] = int(temp_charger_hex, 16) / 100.0
    
    return result

def decode_packet_0x02(payload_hex):
    """
    Packet 0x02: Weather Data (co 5 minut)
    Format: 02 TTTT HHHH BBBB
    
    Przykład: 0209D911380968
    - 02 = typ pakietu
    - 09D9 = Temp SHT45 (2521 / 100 = 25.21°C)
    - 1138 = Humidity (4408 / 100 = 44.08%)
    - 0968 = Temp BMP390 (2408 / 100 = 24.08°C)
    """
    if len(payload_hex) < 14:
        return None
    
    packet_type = payload_hex[0:2]
    if packet_type != "02":
        return None
    
    temp_sht45_hex = payload_hex[2:6]
    humidity_hex = payload_hex[6:10]
    temp_bmp390_hex = payload_hex[10:14]
    
    temp_sht45 = int(temp_sht45_hex, 16) / 100.0
    humidity = int(humidity_hex, 16) / 100.0
    temp_bmp390 = int(temp_bmp390_hex, 16) / 100.0
    
    return {
        "packet_type": "0x02",
        "packet_name": "Weather Data",
        "temperature": temp_sht45,
        "humidity": humidity,
        "temp_bmp390": temp_bmp390
    }

def decode_packet_0x11(payload_hex):
    """
    Packet 0x11: Power Module Diagnostics
    Format: 11 [dane diagnostyczne]
    """
    if len(payload_hex) < 4:
        return None
    
    packet_type = payload_hex[0:2]
    if packet_type != "11":
        return None
    
    return {
        "packet_type": "0x11",
        "packet_name": "Power Diagnostics",
        "raw_data": payload_hex[2:]
    }

def decode_packet_0x12(payload_hex):
    """
    Packet 0x12: Light + Pressure (co 10 minut)
    Format: 12 LLLLLLLL WWWW [PPPP]
    
    Przykład: 12000000002733
    - 12 = typ pakietu
    - 00000000 = Lux (4 bajty)
    - 2733 = White ratio (10035 / 100 = 100.35)
    - [PPPP] = opcjonalnie ciśnienie
    """
    if len(payload_hex) < 14:
        return None
    
    packet_type = payload_hex[0:2]
    if packet_type != "12":
        return None
    
    lux_hex = payload_hex[2:10]
    white_ratio_hex = payload_hex[10:14]
    
    lux = int(lux_hex, 16)
    white_ratio = int(white_ratio_hex, 16) / 100.0
    
    result = {
        "packet_type": "0x12",
        "packet_name": "Light + Pressure",
        "lux": lux,
        "white_ratio": white_ratio
    }
    
    if len(payload_hex) >= 18:
        pressure_hex = payload_hex[14:18]
        result["pressure"] = int(pressure_hex, 16) / 100.0
    
    return result

def decode_sudden_packet(payload_hex):
    """
    Sudden Packets (0x22-0xF2): Pojedyncze odczyty
    Format: XX VVVV
    
    Przykład: 2200550006
    - 22 = typ (Sudden Humidity)
    - 0055 = wartość (85 / 100 = 0.85%)
    - 0006 = ???
    """
    if len(payload_hex) < 6:
        return None
    
    packet_type = payload_hex[0:2]
    
    sudden_types = {
        "22": ("Sudden Humidity", 100.0, "%"),
        "32": ("Sudden SHT45 Temp", 100.0, "°C"),
        "42": ("Sudden BMP390 Temp", 100.0, "°C"),
        "52": ("Sudden VEML7700 Lux", 1.0, "lux"),
        "62": ("Sudden White Ratio", 100.0, ""),
        "72": ("Sudden BMP390 Pressure", 100.0, "hPa"),
        "82": ("Sudden Analog IN_1", 100.0, "V"),
        "92": ("Sudden Analog IN_2", 100.0, "V"),
        "A2": ("Sudden Data 1", 1.0, ""),
        "B2": ("Sudden Data 2", 1.0, ""),
        "C2": ("Sudden Data 3", 1.0, ""),
        "D2": ("Sudden Data 4", 1.0, ""),
        "E2": ("Sudden Data 5", 1.0, ""),
        "F2": ("Last Message downlink", 1.0, "")
    }
    
    if packet_type not in sudden_types:
        return None
    
    name, divisor, unit = sudden_types[packet_type]
    
    value_hex = payload_hex[2:6]
    value = int(value_hex, 16) / divisor
    
    return {
        "packet_type": f"0x{packet_type}",
        "packet_name": name,
        "value": value,
        "unit": unit,
        "raw_suffix": payload_hex[6:] if len(payload_hex) > 6 else None
    }

# ========== MQTT CALLBACKS ==========

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("🚀 LoRa Receiver - Odbieranie danych od kolegi")
        print(f"📡 Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print("\nNaciśnij Ctrl+C aby zatrzymać\n")
        print("✅ Połączono z MQTT!")
        print(f"📡 Nasłuchiwanie: {MQTT_TOPIC}")
        print("=" * 70)
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Błąd połączenia: {rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        
        # Podstawowe info
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\n📨 [{timestamp}]")
        
        # Payload
        if 'data' not in data:
            print("⚠️  Brak pola 'data'")
            return
        
        payload_b64 = data['data']
        payload_bytes = base64.b64decode(payload_b64)
        payload_hex = payload_bytes.hex().upper()
        
        print(f"📦 Payload HEX: {payload_hex}")
        
        # Sygnał
        rssi = -100
        snr = 0
        if 'rxInfo' in data and len(data['rxInfo']) > 0:
            rssi = data['rxInfo'][0].get('rssi', -100)
            snr = data['rxInfo'][0].get('snr', 0)
        
        # ========== DEKODOWANIE ==========
        decoded = None
        
        # Próbuj wszystkich dekoderów
        decoders = [
            decode_packet_0x01,
            decode_packet_0x02,
            decode_packet_0x11,
            decode_packet_0x12,
            decode_sudden_packet
        ]
        
        for decoder in decoders:
            decoded = decoder(payload_hex)
            if decoded:
                break
        
        if not decoded:
            print(f"⚠️  Nieznany typ packetu: 0x{payload_hex[0:2] if len(payload_hex) >= 2 else 'BRAK'}")
            print("-" * 70)
            return
        
        # ========== WYŚWIETL ZDEKODOWANE DANE ==========
        print(f"✅ Zdekodowano: {decoded['packet_name']}")
        
        # PACKET 0x01 - Power Module
        if decoded['packet_type'] == '0x01':
            print(f"   🔋 Cell 1: {decoded['cell1_voltage']:.3f}V")
            print(f"   🔋 Cell 2: {decoded['cell2_voltage']:.3f}V")
            print(f"   🔋 Cell 3: {decoded['cell3_voltage']:.3f}V")
            if 'pack_temp_bms' in decoded:
                print(f"   🌡️  Temp BMS: {decoded['pack_temp_bms']:.2f}°C")
            if 'pack_temp_charger' in decoded:
                print(f"   🌡️  Temp Charger: {decoded['pack_temp_charger']:.2f}°C")
        
        # PACKET 0x02 - Weather Data
        elif decoded['packet_type'] == '0x02':
            print(f"   🌡️  Temperatura: {decoded['temperature']:.2f}°C")
            print(f"   💧 Wilgotność:   {decoded['humidity']:.2f}%")
            print(f"   🌡️  Temp BMP390:  {decoded['temp_bmp390']:.2f}°C")
        
        # PACKET 0x11 - Power Diagnostics
        elif decoded['packet_type'] == '0x11':
            print(f"   📊 Raw data: {decoded['raw_data']}")
        
        # PACKET 0x12 - Light + Pressure
        elif decoded['packet_type'] == '0x12':
            print(f"   💡 Lux: {decoded['lux']}")
            print(f"   ⚪ White Ratio: {decoded['white_ratio']:.2f}")
            if 'pressure' in decoded:
                print(f"   ⏲️  Ciśnienie: {decoded['pressure']:.2f} hPa")
        
        # SUDDEN PACKETS
        elif decoded['packet_type'].startswith('0x'):
            print(f"   📊 Wartość: {decoded['value']:.2f} {decoded['unit']}")
            if decoded['raw_suffix']:
                print(f"   🔍 Suffix: {decoded['raw_suffix']}")
        
        # Sygnał
        print(f"📶 RSSI: {rssi} dBm, SNR: {snr} dB")
        print("-" * 70)
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()

def main():
    client = mqtt.Client(client_id="lora_simple_decoder")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n⛔ Zatrzymywanie...")
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
    finally:
        client.disconnect()
        print("👋 Zamknięto")

if __name__ == "__main__":
    main()
