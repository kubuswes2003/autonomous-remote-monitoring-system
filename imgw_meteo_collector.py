#!/usr/bin/env python3
"""
IMGW Meteo Collector → MQTT Bridge
Pobiera dane meteorologiczne z IMGW-PIB i wysyła do MQTT
mqtt_to_influxdb.py następnie zapisze je do InfluxDB (tak jak dane z LoRa)
"""

import os
import paho.mqtt.client as mqtt
import requests
import json
from datetime import datetime
import sys

# ========== KONFIGURACJA ==========

# Poznań-Ławica
STATION_ID = "station_lawica"  # ASCII (bez polskich znaków)
STATION_NAME = "EPPO - Lotnisko Ławica"
STATION_LAT = 52.421
STATION_LNG = 16.826

# IMGW-PIB API
IMGW_API_URL = "https://danepubliczne.imgw.pl/api/data/synop"

# MQTT (lokalny broker - tak jak LoRa bridge)
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_TOPIC = "weather/station/data"  # Ten sam topic co LoRa!

# ========== FUNKCJE ==========

def get_imgw_data():
    """
    Pobiera aktualne dane ze wszystkich stacji IMGW
    Szuka stacji Poznań
    """
    try:
        print(f"📡 Pobieranie danych z IMGW-PIB...")
        print(f"   URL: {IMGW_API_URL}")
        
        response = requests.get(IMGW_API_URL, timeout=30)
        response.raise_for_status()
        
        stations = response.json()
        print(f"✅ Pobrano dane z {len(stations)} stacji")
        
        # Szukaj stacji Poznań
        poznan_station = None
        for station in stations:
            station_name = station.get('stacja', '').lower()
            if 'pozna' in station_name:  # "Poznań" lub "Poznan"
                poznan_station = station
                print(f"✅ Znaleziono stację: {station.get('stacja')}")
                break
        
        if not poznan_station:
            print("❌ Nie znaleziono stacji Poznań w danych IMGW")
            return None
        
        # Wyciągnij dane
        result = {
            'station_name': poznan_station.get('stacja'),
            'temperature': parse_float(poznan_station.get('temperatura')),
            'humidity': parse_float(poznan_station.get('wilgotnosc_wzgledna')),
            'pressure': parse_float(poznan_station.get('cisnienie')),
            'wind_speed': parse_float(poznan_station.get('predkosc_wiatru')),
            'wind_direction': parse_float(poznan_station.get('kierunek_wiatru'))
        }
        
        print(f"\n📊 Dane ze stacji {result['station_name']}:")
        print(f"   🌡️  Temperatura: {result['temperature']}°C")
        print(f"   💧 Wilgotność: {result['humidity']}%")
        print(f"   ⚖️  Ciśnienie: {result['pressure']} hPa")
        print(f"   💨 Wiatr: {result['wind_speed']} m/s @ {result['wind_direction']}°")
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd pobierania danych: {e}")
        import traceback
        traceback.print_exc()
        return None

def parse_float(value):
    """
    Bezpiecznie konwertuje wartość na float
    """
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def send_to_mqtt(weather_data):
    """
    Wysyła dane do MQTT w TAKIM SAMYM FORMACIE jak LoRa bridge
    """
    try:
        # Przygotuj JSON (identyczny format jak lora_receiver_bridge.py)
        payload = {
            "station_id": STATION_ID,
            "timestamp": datetime.now().isoformat(),
            "sensors": {
                "temperature": weather_data['temperature'] if weather_data['temperature'] is not None else 20.0,
                "humidity": weather_data['humidity'] if weather_data['humidity'] is not None else 50.0,
                "pressure": weather_data['pressure'] if weather_data['pressure'] is not None else 1013.25,
                "wind_speed": (weather_data['wind_speed'] / 3.6) if weather_data['wind_speed'] is not None else 0.0,  # km/h → m/s
                "wind_direction": weather_data['wind_direction'] if weather_data['wind_direction'] is not None else 0
            },
            "battery_voltage": 0.0,  # IMGW nie ma baterii (zasilanie sieciowe)
            "signal_strength": -50,  # Stała wartość (zawsze dobre połączenie)
            "lat": STATION_LAT,
            "lng": STATION_LNG,
            "location": STATION_NAME,
            "is_lora": False,  # To nie jest LoRa, to IMGW
            "imgw_metadata": {
                "source": "IMGW-PIB",
                "station_name": weather_data['station_name'],
                "api_url": IMGW_API_URL
            }
        }
        
        # Połącz z MQTT
        client = mqtt.Client(client_id="imgw_collector")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Wyślij
        payload_str = json.dumps(payload)
        result = client.publish(MQTT_TOPIC, payload_str, qos=1)
        
        if result.rc == 0:
            print(f"\n✅ Wysłano do MQTT:")
            print(f"   Broker: {MQTT_BROKER}:{MQTT_PORT}")
            print(f"   Topic: {MQTT_TOPIC}")
            print(f"   Station: {STATION_ID}")
            print(f"\n💡 Teraz mqtt_to_influxdb.py zapisze to do InfluxDB automatycznie!")
        else:
            print(f"❌ Błąd wysyłania do MQTT: {result.rc}")
            return False
        
        client.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Błąd wysyłania do MQTT: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    Główna funkcja
    """
    print("=" * 70)
    print(f"🌤️  IMGW → MQTT Bridge - {STATION_NAME}")
    print(f"⏰ Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Pobierz dane
    weather_data = get_imgw_data()
    
    if weather_data is None:
        print("❌ Nie udało się pobrać danych")
        sys.exit(1)
    
    # Wyślij do MQTT
    success = send_to_mqtt(weather_data)
    
    if success:
        print("=" * 70)
        print("✅ Sukces! Dane wysłane do MQTT.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("=" * 70)
        print("❌ Błąd! Dane nie zostały wysłane.")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
