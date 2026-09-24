#!/usr/bin/env python3
"""
Meteo Historical Import - Poznań-Ławica (EPPO)
Jednorazowy import ostatnich 30 dni danych meteorologicznych do InfluxDB
Uruchom raz: python3 meteo_import_historical.py
"""

import os
from meteostat import Point, Hourly
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point as InfluxPoint
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd

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

# Okres danych
DAYS_BACK = 30

# ========== FUNKCJE ==========

def get_historical_data():
    """
    Pobiera dane historyczne z ostatnich 30 dni
    """
    try:
        end = datetime.now()
        start = end - timedelta(days=DAYS_BACK)
        
        print(f"📡 Pobieranie danych historycznych dla {STATION_NAME}")
        print(f"   Okres: {start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}")
        print(f"   Lokalizacja: {STATION_LOCATION.lat}, {STATION_LOCATION.lon}")
        
        # Pobierz dane godzinowe
        data = Hourly(STATION_LOCATION, start, end)
        df = data.fetch()
        
        if df.empty:
            print("⚠️  Brak danych historycznych")
            return None
        
        print(f"✅ Pobrano {len(df)} rekordów")
        print(f"   Pierwszy: {df.index[0].strftime('%Y-%m-%d %H:%M')}")
        print(f"   Ostatni: {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
        
        # Pokaż statystyki
        print(f"\n📊 Statystyki danych:")
        print(f"   Temperatura: {df['temp'].min():.1f}°C - {df['temp'].max():.1f}°C (średnia: {df['temp'].mean():.1f}°C)")
        print(f"   Wilgotność: {df['rhum'].min():.0f}% - {df['rhum'].max():.0f}% (średnia: {df['rhum'].mean():.0f}%)")
        print(f"   Ciśnienie: {df['pres'].min():.1f} - {df['pres'].max():.1f} hPa (średnia: {df['pres'].mean():.1f} hPa)")
        
        return df
        
    except Exception as e:
        print(f"❌ Błąd pobierania danych: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_to_influxdb(df):
    """
    Zapisuje dane historyczne do InfluxDB
    """
    try:
        # Połącz z InfluxDB
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        print(f"\n💾 Zapisywanie do InfluxDB...")
        print(f"   Bucket: {INFLUX_BUCKET}")
        print(f"   Station: {STATION_ID}")
        
        # Przygotuj punkty danych
        points = []
        skipped = 0
        
        for timestamp, row in df.iterrows():
            # Sprawdź czy mamy przynajmniej temperaturę lub wilgotność
            if pd.isna(row['temp']) and pd.isna(row['rhum']):
                skipped += 1
                continue
            
            # Stwórz punkt
            point = InfluxPoint("weather_measurement") \
                .tag("station_id", STATION_ID) \
                .time(timestamp)
            
            # Dodaj pola (tylko jeśli nie są NaN)
            if not pd.isna(row['temp']):
                point.field("temperature", float(row['temp']))
            
            if not pd.isna(row['rhum']):
                point.field("humidity", float(row['rhum']))
            
            if not pd.isna(row['pres']):
                point.field("pressure", float(row['pres']))
            
            if not pd.isna(row['wspd']):
                # Konwertuj km/h na m/s
                wind_speed_ms = float(row['wspd']) / 3.6
                point.field("wind_speed", wind_speed_ms)
            
            if not pd.isna(row['wdir']):
                point.field("wind_direction", int(row['wdir']))
            
            points.append(point)
            
            # Zapisuj w partiach po 500 rekordów
            if len(points) >= 500:
                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
                print(f"   ✓ Zapisano {len(points)} rekordów...")
                points = []
        
        # Zapisz pozostałe
        if points:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
            print(f"   ✓ Zapisano {len(points)} rekordów...")
        
        if skipped > 0:
            print(f"   ⚠️  Pominięto {skipped} rekordów (brak danych)")
        
        print(f"✅ Zapisano łącznie {len(df) - skipped} rekordów")
        
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
    print(f"📦 Import Historycznych Danych - {STATION_NAME}")
    print(f"⏰ Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Okres: Ostatnie {DAYS_BACK} dni")
    print("=" * 70)
    
    # Potwierdź przed importem
    print(f"\n⚠️  UWAGA: To doda ~{DAYS_BACK * 24} rekordów do bazy danych!")
    response = input("Kontynuować? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("❌ Anulowano")
        return
    
    print()
    
    # Pobierz dane historyczne
    df = get_historical_data()
    
    if df is None or df.empty:
        print("❌ Nie udało się pobrać danych historycznych")
        return
    
    # Zapisz do InfluxDB
    success = save_to_influxdb(df)
    
    if success:
        print("=" * 70)
        print("✅ Import zakończony sukcesem!")
        print("=" * 70)
        print("\n📊 Możesz teraz:")
        print("   1. Sprawdzić dane w Grafana")
        print("   2. Zobaczyć wykres na stronie")
        print("   3. Usunąć ten skrypt (już nie jest potrzebny)")
    else:
        print("=" * 70)
        print("❌ Import zakończony błędem")
        print("=" * 70)

if __name__ == "__main__":
    main()
