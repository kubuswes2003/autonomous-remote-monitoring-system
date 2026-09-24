#!/usr/bin/env python3
"""
LoRa Receiver Bridge - IMPROVED VERSION
Odbiera dane z LoRa (10.58.40.99) i przekazuje do lokalnego MQTT (localhost)
w formacie kompatybilnym z emulatorami i web UI.

POPRAWKI:
- Poprawione dekodowanie pakietu 0x12 (pressure był w złym miejscu)
- Dodana obsługa pakietu 0x22 (wind speed, precipitation, analog inputs)
- Lepsze nazewnictwo stacji (LORA_XXXXXX zamiast "Station XXXXXX")
- Więcej szczegółów w metadanych
- SIGNED INT16 dla temperatur (obsługa wartości ujemnych)
"""

import os
import paho.mqtt.client as mqtt
import json
import base64
from datetime import datetime

# ========== KONFIGURACJA ZDALNEGO BROKERA (LoRa) ==========
REMOTE_MQTT_BROKER = os.getenv("REMOTE_MQTT_BROKER", "localhost")
REMOTE_MQTT_PORT = 1883
REMOTE_MQTT_USERNAME = os.getenv("REMOTE_MQTT_USERNAME", "")
REMOTE_MQTT_PASSWORD = os.getenv("REMOTE_MQTT_PASSWORD", "")
REMOTE_MQTT_TOPIC = "application/bcb75d00-e41b-4f24-9891-2d26072205e2/device/+/event/up"

# ========== KONFIGURACJA LOKALNEGO BROKERA ==========
LOCAL_MQTT_BROKER = os.getenv("LOCAL_MQTT_BROKER", "localhost")
LOCAL_MQTT_PORT = 1883
LOCAL_MQTT_TOPIC = "weather/station/data"

# ========== HELPER FUNCTIONS ==========

def hex_to_int16_signed(hex_str):
    """Konwertuje 4-znakowy hex string na signed int16"""
    return int.from_bytes(bytes.fromhex(hex_str), 'big', signed=True)

def hex_to_int32_signed(hex_str):
    """Konwertuje 8-znakowy hex string na signed int32"""
    return int.from_bytes(bytes.fromhex(hex_str), 'big', signed=True)

# ========== DEKODERY PAKIETÓW ==========

def decode_packet_0x01(payload_hex):
    """
    Power Module (0x01) - every 6H
    Format: 01 CCCC CCCC CCCC SSSS TTTT TTTT
    - Cell voltages (3x 2 bytes) in mV
    - Pack temp BMS side (2 bytes) in 0.01°C
    - Pack temp charger side (2 bytes) in 0.01°C
    """
    if len(payload_hex) < 14 or payload_hex[0:2] != "01":
        return None
    
    cell1 = int(payload_hex[2:6], 16) / 1000.0
    cell2 = int(payload_hex[6:10], 16) / 1000.0
    cell3 = int(payload_hex[10:14], 16) / 1000.0
    
    result = {
        "packet_type": "0x01",
        "cell1_voltage": cell1,
        "cell2_voltage": cell2,
        "cell3_voltage": cell3,
        "battery_voltage": (cell1 + cell2 + cell3)
    }
    
    if len(payload_hex) >= 22:
        # Temperatury mogą być ujemne - użyj signed
        result["pack_temp_bms"] = hex_to_int16_signed(payload_hex[14:18]) / 100.0
        result["pack_temp_charger"] = hex_to_int16_signed(payload_hex[18:22]) / 100.0
    
    return result

def decode_packet_0x02(payload_hex):
    """
    Weather Data (0x02) - every 5 min
    Format: 02 TTTT HHHH BBBB
    Example: 02091D0E940929
    - SHT45 temperature (2 bytes) in 0.01°C - SIGNED
    - SHT45 humidity (2 bytes) in 0.01%
    - BMP390 temperature (2 bytes) in 0.01°C - SIGNED
    """
    if len(payload_hex) < 14 or payload_hex[0:2] != "02":
        return None
    
    return {
        "packet_type": "0x02",
        "temperature": hex_to_int16_signed(payload_hex[2:6]) / 100.0,     # SHT45 - SIGNED
        "humidity": int(payload_hex[6:10], 16) / 100.0,                   # SHT45 - unsigned (0-100%)
        "temp_bmp390": hex_to_int16_signed(payload_hex[10:14]) / 100.0    # BMP390 - SIGNED
    }

def decode_packet_0x11(payload_hex):
    """
    Power Module Diagnostics (0x11) - every 6H
    Format: 11 [various diagnostic data]
    VBUS voltage, Charger status, current_BMS
    Dokładny format nieznany - wyświetlamy surowe dane
    """
    if len(payload_hex) < 4 or payload_hex[0:2] != "11":
        return None
    
    result = {
        "packet_type": "0x11",
        "module": "Power Module Diagnostics",
        "raw_data": payload_hex[2:]  # Reszta jako surowe dane
    }
    
    return result

def decode_packet_0x12(payload_hex):
    """
    Light + Pressure (0x12) - every 10 min
    Format: 12 LLLLLLLL WWWW PPPPPPPP
    Example: 12000120CC039200018AFC
    - VEML7700 Lux (4 bytes) - unsigned
    - VEML7700 white ratio (2 bytes) in 0.01 - unsigned
    - BMP390 pressure (4 bytes) in 0.01 hPa - unsigned
    """
    if len(payload_hex) < 22 or payload_hex[0:2] != "12":
        return None
    
    result = {
        "packet_type": "0x12",
        "lux": int(payload_hex[2:10], 16),                    # 4 bytes - unsigned
        "white_ratio": int(payload_hex[10:14], 16) / 100.0,   # 2 bytes - unsigned
        "pressure": int(payload_hex[14:22], 16) / 100.0       # 4 bytes - unsigned
    }
    
    return result

def decode_packet_0x22(payload_hex):
    """
    Wind + Rain + Analog (0x22) - every 15 min
    Format: 22 WWWW RRRR AAAA BBBB
    - Wind speed 15min avg (2 bytes) in 0.01 m/s - unsigned
    - Precipitation last 15min (2 bytes) in 0.01 mm - unsigned
    - Analog IN_1 tics in 15min (2 bytes) - unsigned
    - Analog IN_2 tics in 15min (2 bytes) - unsigned
    """
    if len(payload_hex) < 18 or payload_hex[0:2] != "22":
        return None
    
    return {
        "packet_type": "0x22",
        "wind_speed_avg": int(payload_hex[2:6], 16) / 100.0,
        "precipitation_mm": int(payload_hex[6:10], 16) / 100.0,
        "analog_in1_tics": int(payload_hex[10:14], 16),
        "analog_in2_tics": int(payload_hex[14:18], 16)
    }

def decode_sudden_packet(payload_hex):
    """
    Sudden packets (0x32-0xF2) - on demand
    Format: XX VVVV (typ + wartość 2 bajty)
    """
    if len(payload_hex) < 6:
        return None
    
    packet_type = payload_hex[0:2]
    
    # (field_name, divisor, unit, description, is_signed)
    sudden_map = {
        "32": ("temperature", 100.0, "°C", "Sudden SHT45 Temp", True),
        "42": ("humidity", 100.0, "%", "Sudden SHT45 Humidity", False),
        "52": ("temp_bmp390", 100.0, "°C", "Sudden BMP390 Temp", True),
        "62": ("lux", 1.0, "lux", "Sudden VEML7700 Lux", False),
        "72": ("white_ratio", 100.0, "", "Sudden VEML7700 White Ratio", False),
        "82": ("pressure", 100.0, "hPa", "Sudden BMP390 Pressure", False),
        "92": ("analog_in1", 100.0, "V", "Sudden Analog IN_1", False),
        "A2": ("analog_in2", 100.0, "V", "Sudden Analog IN_2", False),
    }
    
    if packet_type not in sudden_map:
        return None
    
    field, divisor, unit, description, is_signed = sudden_map[packet_type]
    
    if is_signed:
        value = hex_to_int16_signed(payload_hex[2:6]) / divisor
    else:
        value = int(payload_hex[2:6], 16) / divisor
    
    return {
        "packet_type": f"0x{packet_type}",
        "sudden_field": field,
        "sudden_value": value,
        "unit": unit,
        "description": description
    }

# ========== KLIENTY MQTT ==========

local_client = mqtt.Client(client_id="lora_bridge_local")
message_count = 0
last_values = {}  # Przechowuje ostatnie wartości dla każdej stacji

def on_local_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Połączono z lokalnym MQTT ({LOCAL_MQTT_BROKER})")
    else:
        print(f"❌ Błąd lokalnego MQTT: {rc}")

def on_remote_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Połączono z LoRa MQTT ({REMOTE_MQTT_BROKER})")
        print(f"📡 Nasłuchiwanie: {REMOTE_MQTT_TOPIC}")
        print("=" * 70)
        client.subscribe(REMOTE_MQTT_TOPIC)
    else:
        print(f"❌ Błąd LoRa MQTT: {rc}")

def get_or_create_station_data(station_id):
    """Zwraca lub tworzy domyślne dane stacji"""
    if station_id not in last_values:
        last_values[station_id] = {
            "temperature": None,
            "humidity": None,
            "pressure": None,
            "wind_speed": None,
            "temp_bmp390": None,
            "lux": None,
            "white_ratio": None,
            "precipitation_mm": None,
            "battery_voltage": 4.0,
            "lora_metadata": {}  # Cache dla metadanych LoRa
        }
    return last_values[station_id]

def on_remote_message(client, userdata, msg):
    global message_count
    message_count += 1
    
    try:
        data = json.loads(msg.payload.decode())
        
        if 'data' not in data:
            return
        
        payload_hex = base64.b64decode(data['data']).hex().upper()
        
        # Device info
        device_info = data.get('deviceInfo', {})
        dev_eui = device_info.get('devEui', 'UNKNOWN')
        device_name = device_info.get('deviceName', 'LoRa Station')
        
        # Station ID: station_ + pełny DevEUI (kompatybilne z bazą danych)
        station_id = f"station_{dev_eui}"
        
        # Location (default Poznań)
        lat, lng = 52.4064, 16.9252
        if 'rxInfo' in data and len(data['rxInfo']) > 0:
            rx_info = data['rxInfo'][0]
            if 'location' in rx_info:
                lat = rx_info['location'].get('latitude', lat)
                lng = rx_info['location'].get('longitude', lng)
        
        # Signal
        rssi = -100
        snr = 0
        if 'rxInfo' in data and len(data['rxInfo']) > 0:
            rssi = data['rxInfo'][0].get('rssi', -100)
            snr = data['rxInfo'][0].get('snr', 0)
        
        # Pobierz ostatnie wartości dla tej stacji
        station_values = get_or_create_station_data(station_id)
        
        # Dekoduj pakiet
        decoded = None
        for decoder in [decode_packet_0x01, decode_packet_0x02, decode_packet_0x11,
                       decode_packet_0x12, decode_packet_0x22, decode_sudden_packet]:
            decoded = decoder(payload_hex)
            if decoded:
                break
        
        if not decoded:
            print(f"⚠️  [{message_count}] Nieznany packet: 0x{payload_hex[0:2] if len(payload_hex) >= 2 else 'BRAK'}")
            print(f"   • Długość HEX: {len(payload_hex)} znaków")
            print(f"   • Pełny payload: {payload_hex}")
            return
        
        # Wyświetl surowy HEX payload
        print(f"\n{'='*70}")
        print(f"📨 [{message_count}] OTRZYMANO PAKIET LoRa")
        print(f"{'='*70}")
        print(f"🔸 Station ID: {station_id}")
        print(f"🔸 Device EUI: {dev_eui}")
        print(f"🔸 Surowy HEX: {payload_hex}")
        print(f"🔸 Typ pakietu: {decoded['packet_type']}")
        
        # Zaktualizuj wartości stacji na podstawie pakietu i wyświetl zdekodowane dane
        if decoded['packet_type'] == '0x01':
            # Power Module - aktualizuj baterię i metadata
            station_values['battery_voltage'] = decoded.get('battery_voltage', 4.0)
            station_values['lora_metadata']['power_module'] = {
                'cell1': decoded['cell1_voltage'],
                'cell2': decoded['cell2_voltage'],
                'cell3': decoded['cell3_voltage']
            }
            if 'pack_temp_bms' in decoded:
                station_values['lora_metadata']['power_module']['temp_bms'] = decoded['pack_temp_bms']
                station_values['lora_metadata']['power_module']['temp_charger'] = decoded['pack_temp_charger']
            
            print(f"\n🔋 ZDEKODOWANE DANE (Power Module):")
            print(f"   • Cell 1 voltage: {decoded['cell1_voltage']:.3f}V")
            print(f"   • Cell 2 voltage: {decoded['cell2_voltage']:.3f}V")
            print(f"   • Cell 3 voltage: {decoded['cell3_voltage']:.3f}V")
            print(f"   • Total battery: {decoded['battery_voltage']:.3f}V")
            if 'pack_temp_bms' in decoded:
                print(f"   • Pack temp BMS: {decoded['pack_temp_bms']:.2f}°C")
                print(f"   • Pack temp Charger: {decoded['pack_temp_charger']:.2f}°C")
        
        elif decoded['packet_type'] == '0x11':
            # Power Module Diagnostics - zapisz do metadata
            station_values['lora_metadata']['power_diagnostics'] = {
                'module': decoded['module'],
                'raw_data': decoded['raw_data']
            }
            
            print(f"\n🔧 ZDEKODOWANE DANE (Power Diagnostics):")
            print(f"   • Module: {decoded['module']}")
            print(f"   • Raw data: {decoded['raw_data']}")
        
        elif decoded['packet_type'] == '0x02':
            station_values['temperature'] = decoded['temperature']
            station_values['humidity'] = decoded['humidity']
            station_values['temp_bmp390'] = decoded['temp_bmp390']
            station_values['lora_metadata']['temp_bmp390'] = decoded['temp_bmp390']
            
            print(f"\n🌡️  ZDEKODOWANE DANE (Weather Data):")
            print(f"   • Temperatura SHT45: {decoded['temperature']:.2f}°C")
            print(f"   • Wilgotność SHT45: {decoded['humidity']:.2f}%")
            print(f"   • Temperatura BMP390: {decoded['temp_bmp390']:.2f}°C")
        
        elif decoded['packet_type'] == '0x12':
            station_values['lux'] = decoded['lux']
            station_values['white_ratio'] = decoded['white_ratio']
            station_values['pressure'] = decoded['pressure']
            station_values['lora_metadata']['lux'] = decoded['lux']
            station_values['lora_metadata']['white_ratio'] = decoded['white_ratio']
            
            print(f"\n💡 ZDEKODOWANE DANE (Light + Pressure):")
            print(f"   • Lux: {decoded['lux']}")
            print(f"   • White Ratio: {decoded['white_ratio']:.2f}")
            print(f"   • Ciśnienie BMP390: {decoded['pressure']:.2f} hPa")
        
        elif decoded['packet_type'] == '0x22':
            station_values['wind_speed'] = decoded['wind_speed_avg']
            station_values['precipitation_mm'] = decoded['precipitation_mm']
            
            print(f"\n💨 ZDEKODOWANE DANE (Wind + Rain):")
            print(f"   • Średnia prędkość wiatru (15min): {decoded['wind_speed_avg']:.2f} m/s")
            print(f"   • Opady (15min): {decoded['precipitation_mm']:.2f} mm")
            print(f"   • Analog IN_1 tics: {decoded['analog_in1_tics']}")
            print(f"   • Analog IN_2 tics: {decoded['analog_in2_tics']}")
        
        elif decoded['packet_type'].startswith('0x') and 'sudden_field' in decoded:
            field = decoded['sudden_field']
            value = decoded['sudden_value']
            station_values[field] = value
            
            print(f"\n⚡ ZDEKODOWANE DANE (Sudden Reading):")
            print(f"   • {decoded['description']}: {value:.2f} {decoded['unit']}")
            print(f"   • Pole: {field}")
        
        # Przygotuj JSON dla lokalnego MQTT (format jak emulatory)
        output = {
            "station_id": station_id,
            "timestamp": datetime.now().isoformat(),
            "sensors": {
                "temperature": station_values['temperature'] if station_values['temperature'] is not None else 20.0,
                "humidity": station_values['humidity'] if station_values['humidity'] is not None else 50.0,
                "pressure": station_values['pressure'] if station_values['pressure'] is not None else 1013.25,
                "wind_speed": station_values['wind_speed'] if station_values['wind_speed'] is not None else 0.0,
                "wind_direction": 0  # Brak kierunku wiatru w obecnych pakietach
            },
            "battery_voltage": station_values['battery_voltage'],
            "signal_strength": rssi,
            "lat": lat,
            "lng": lng,
            "location": device_name,
            "is_lora": True,
            "lora_metadata": {
                "dev_eui": dev_eui,
                "device_name": device_name,
                "snr": snr,
                "packet_type": decoded['packet_type'],
                "raw_hex": payload_hex,
                **station_values['lora_metadata']  # Dodaj wszystkie cache'owane metadata
            }
        }
        
        # Wyślij do lokalnego MQTT
        result = local_client.publish(LOCAL_MQTT_TOPIC, json.dumps(output))
        
        # Pokaż najważniejsze pola z wysyłanego JSON'a
        print(f"\n📤 WYSYŁAM DO LOKALNEGO MQTT:")
        print(f"   • Station ID: {output['station_id']}")
        print(f"   • Temperatura: {output['sensors']['temperature']:.2f}°C")
        print(f"   • Wilgotność: {output['sensors']['humidity']:.2f}%")
        print(f"   • Ciśnienie: {output['sensors']['pressure']:.2f} hPa")
        print(f"   • Prędkość wiatru: {output['sensors']['wind_speed']:.2f} m/s")
        print(f"   • Bateria: {output['battery_voltage']:.2f}V")
        print(f"   • RSSI: {output['signal_strength']} dBm")
        print(f"   • SNR: {output['lora_metadata']['snr']:.1f} dB")
        
        # Pokaż dodatkowe metadane jeśli są w cache
        metadata = output['lora_metadata']
        if 'temp_bmp390' in metadata:
            print(f"   • Temp BMP390: {metadata['temp_bmp390']:.2f}°C")
        if 'lux' in metadata:
            print(f"   • Lux: {metadata['lux']}")
        if 'white_ratio' in metadata:
            print(f"   • White Ratio: {metadata['white_ratio']:.2f}")
        if 'power_module' in metadata:
            print(f"   • Power Module: Cell1={metadata['power_module']['cell1']:.3f}V, Cell2={metadata['power_module']['cell2']:.3f}V, Cell3={metadata['power_module']['cell3']:.3f}V")
        if 'power_diagnostics' in metadata:
            print(f"   • Power Diagnostics: {metadata['power_diagnostics']['raw_data']}")
        
        if result.rc == 0:
            print(f"\n✅ Pomyślnie wysłano do MQTT")
        else:
            print(f"\n❌ Błąd wysyłania: {result.rc}")
        
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"❌ Błąd przetwarzania: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("🚀 LoRa → MQTT Bridge (IMPROVED + SIGNED INT FIX)")
    print(f"📡 LoRa: {REMOTE_MQTT_BROKER}:{REMOTE_MQTT_PORT}")
    print(f"💾 Local: {LOCAL_MQTT_BROKER}:{LOCAL_MQTT_PORT}")
    print("\nNaciśnij Ctrl+C aby zatrzymać\n")
    
    # Lokalny klient
    local_client.on_connect = on_local_connect
    try:
        local_client.connect(LOCAL_MQTT_BROKER, LOCAL_MQTT_PORT, 60)
        local_client.loop_start()
    except Exception as e:
        print(f"❌ Błąd lokalnego MQTT: {e}")
        return
    
    # Zdalny klient
    remote_client = mqtt.Client(client_id="lora_bridge_remote_v2")
    remote_client.username_pw_set(REMOTE_MQTT_USERNAME, REMOTE_MQTT_PASSWORD)
    remote_client.on_connect = on_remote_connect
    remote_client.on_message = on_remote_message
    
    try:
        remote_client.connect(REMOTE_MQTT_BROKER, REMOTE_MQTT_PORT, 60)
        remote_client.loop_forever()
    except KeyboardInterrupt:
        print("\n⛔ Zatrzymywanie...")
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
    finally:
        remote_client.disconnect()
        local_client.loop_stop()
        local_client.disconnect()
        print("👋 Zamknięto")

if __name__ == "__main__":
    main()
