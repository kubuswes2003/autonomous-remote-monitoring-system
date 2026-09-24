#!/usr/bin/env python3

import os
import paho.mqtt.client as mqtt
import json
import base64
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ========== KONFIGURACJA MQTT ==========
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = "application/bcb75d00-e41b-4f24-9891-2d26072205e2/device/ac1f09fffe19fc8a/event/up"

# ========== KONFIGURACJA INFLUXDB ==========
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = "weather"
INFLUX_BUCKET = "weather_data"

# ========== INICJALIZACJA INFLUXDB ==========
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def decode_payload(data):
    """
    Dekoduje payload z ChirpStack
    Format może być JSON lub base64
    """
    try:
        # ChirpStack zwraca dane w polu 'data' jako base64
        if 'data' in data:
            payload_b64 = data['data']
            payload_bytes = base64.b64decode(payload_b64)
            
            # Tutaj musisz wiedzieć format danych od kolegi
            # Przykład: jeśli to hex string
            payload_hex = payload_bytes.hex()
            print(f"📦 Payload (hex): {payload_hex}")
            
            # TUTAJ DODAJ DEKODOWANIE SPECYFICZNE DLA WASZEGO FORMATU
            # Przykład: pierwsze 2 bajty = temperatura * 100
            # temp = int(payload_hex[0:4], 16) / 100.0
            
            return payload_hex
        
        # Jeśli payload już jest jako JSON
        if 'object' in data:
            return data['object']
            
        return None
        
    except Exception as e:
        print(f"❌ Błąd dekodowania: {e}")
        return None

def on_connect(client, userdata, flags, rc):
    """Callback po połączeniu z MQTT"""
    if rc == 0:
        print(f"✅ Połączono z brokerem MQTT: {MQTT_BROKER}")
        print(f"📡 Subskrybowanie topic: {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Błąd połączenia. Kod: {rc}")

def on_message(client, userdata, msg):
    """Callback po otrzymaniu wiadomości"""
    try:
        # Parsuj JSON z ChirpStack
        data = json.loads(msg.payload.decode())
        
        print("\n" + "="*70)
        print(f"📨 Otrzymano dane o {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        # Debug: wypisz cały JSON
        print("🔍 Cały payload:")
        print(json.dumps(data, indent=2))
        
        # Wyciągnij informacje
        device_name = data.get('deviceName', 'UNKNOWN')
        dev_eui = data.get('devEUI', 'UNKNOWN')
        
        # Dekoduj payload
        payload = decode_payload(data)
        
        if payload:
            print(f"\n✅ Zdekodowano payload: {payload}")
            
            # TUTAJ MUSISZ DODAĆ PARSOWANIE DANYCH
            # Przykład (dostosuj do formatu kolegi):
            # temperature = ...
            # humidity = ...
            # pressure = ...
            
            # Zapisz do InfluxDB
            # point = Point("weather_measurement") \
            #     .tag("station_id", f"REAL_{dev_eui[-6:]}") \
            #     .field("temperature", temperature) \
            #     .field("humidity", humidity) \
            #     .field("pressure", pressure) \
            #     .time(datetime.utcnow())
            
            # write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            # print("💾 Zapisano do InfluxDB")
        else:
            print("⚠️ Nie udało się zdekodować payload")
            
    except json.JSONDecodeError as e:
        print(f"❌ Błąd parsowania JSON: {e}")
        print(f"Raw payload: {msg.payload}")
    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Główna funkcja"""
    print("🚀 Uruchamianie odbiornika prawdziwych danych...")
    print(f"📡 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"👤 User: {MQTT_USERNAME}")
    print(f"📬 Topic: {MQTT_TOPIC}")
    print("="*70)
    
    # Stwórz klienta MQTT
    client = mqtt.Client(client_id="real_station_receiver")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # Przypisz callbacki
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        # Połącz się
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        print("\n⏳ Oczekiwanie na dane...")
        print("Naciśnij Ctrl+C aby zatrzymać\n")
        
        # Rozpocznij nasłuchiwanie
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n\n⛔ Zatrzymywanie...")
    except Exception as e:
        print(f"\n❌ Błąd połączenia: {e}")
    finally:
        client.disconnect()
        influx_client.close()
        print("👋 Zamknięto połączenia")

if __name__ == "__main__":
    main()
