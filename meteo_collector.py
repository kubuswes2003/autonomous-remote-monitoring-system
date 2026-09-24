#!/usr/bin/env python3
"""
Meteo Collector - Poznań-Ławica (EPPO)
Pobiera dane meteorologiczne z oficjalnej stacji i zapisuje do InfluxDB
Uruchamiany co godzinę przez systemd timer
"""

import os
from meteostat import Point, Hourly
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point as InfluxPoint
from influxdb_client.client.write_api import SYNCHRONOUS
import sys

# ========== KONFIGURACJA ==========

# Poznań-Ławica (EPPO) współrzędne
STATION_LOCATION = Point(52.421, 16.826, 94)  # lat, lon, altitude (m)
STATION_ID = "station_ławica"
STATION_NAME = "EPPO - Lotnisko Ławica"

# InfluxDB
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = "weather"
INFLUX_BUCKET = "weather_data"

# ========== FUNKCJE ==========

def get_latest_weather_data():
    """
    Pobiera dane z ostatniej godziny z Meteostat
    Zwraca: dict z danymi lub None jeśli brak danych
    """
    try:
        # Pobierz dane z ostatnich 2 godzin (dla pewności)
        end = datetime.now()
        start = end - timedelta(hours=2)
        
        print(f"📡 Pobieranie danych dla {STATION_NAME}")
        print(f"   Okres: {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%Y-%m-%d %H:%M')}")
        
        # Pobierz dane godzinowe
        data = Hourly(STATION_LOCATION, start, end)
        data = data.fetch()
        
        if data.empty:
            print("⚠️  Brak danych z Meteostat")
            return None
        
        # Weź ostatni (najnowszy) rekord
        latest = data.iloc[-1]
        timestamp = data.index[-1]
        
        # Wyciągnij dane
        result = {
            'timestamp': timestamp,
            'temperature': latest['temp'] if not pd.isna(latest['temp']) else None,
            'humidity': latest['rhum'] if not pd.isna(latest['rhum']) else None,
            'pressure': latest['pres'] if not pd.isna(latest['pres']) else None,
            'wind_speed': latest['wspd'] if not pd.isna(latest['wspd']) else None,
            'wind_direction': latest['wdir'] if not pd.isna(latest['wdir']) else None
        }
        
        print(f"✅ Pobrano dane z {timestamp.strftime('%Y-%m-%d %H:%M')}")
        print(f"   🌡️  Temperatura: {result['temperature']}°C")
        print(f"   💧 Wilgotność: {result['humidity']}%")
        print(f"   ⚖️  Ciśnienie: {result['pressure']} hPa")
        print(f"   💨 Wiatr: {result['wind_speed']} km/h @ {result['wind_direction']}°")
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd pobierania danych: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_to_influxdb(weather_data):
    """
    Zapisuje dane do InfluxDB
    """
    try:
        # Połącz z InfluxDB
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        # Przygotuj punkt danych (taka sama struktura jak LoRa)
        point = InfluxPoint("weather_measurement") \
            .tag("station_id", STATION_ID) \
            .time(weather_data['timestamp'])
        
        # Dodaj pola (tylko jeśli nie są None)
        if weather_data['temperature'] is not None:
            point.field("temperature", float(weather_data['temperature']))
        
        if weather_data['humidity'] is not None:
            point.field("humidity", float(weather_data['humidity']))
        
        if weather_data['pressure'] is not None:
            point.field("pressure", float(weather_data['pressure']))
        
        if weather_data['wind_speed'] is not None:
            # Meteostat daje km/h, konwertujemy na m/s (jak w LoRa)
            wind_speed_ms = float(weather_data['wind_speed']) / 3.6
            point.field("wind_speed", wind_speed_ms)
        
        if weather_data['wind_direction'] is not None:
            point.field("wind_direction", int(weather_data['wind_direction']))
        
        # Zapisz do InfluxDB
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        
        print(f"✅ Zapisano do InfluxDB:")
        print(f"   Bucket: {INFLUX_BUCKET}")
        print(f"   Station: {STATION_ID}")
        print(f"   Timestamp: {weather_data['timestamp']}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Błąd zapisu do InfluxDB: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    Główna funkcja
    """
    print("=" * 70)
    print(f"🌤️  Meteo Collector - {STATION_NAME}")
    print(f"⏰ Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Pobierz dane
    weather_data = get_latest_weather_data()
    
    if weather_data is None:
        print("❌ Nie udało się pobrać danych")
        sys.exit(1)
    
    # Zapisz do InfluxDB
    success = save_to_influxdb(weather_data)
    
    if success:
        print("=" * 70)
        print("✅ Sukces! Dane zapisane.")
        print("=" * 70)
        sys.exit(0)
    else:
        print("=" * 70)
        print("❌ Błąd! Dane nie zostały zapisane.")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    # Import pandas (wymagane przez meteostat)
    import pandas as pd
    main()
