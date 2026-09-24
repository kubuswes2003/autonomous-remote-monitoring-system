#!/usr/bin/env python3
"""
Mac → InfluxDB (pobierz dane) → ML predict → MQTT publish
Runs every 5 minutes
"""

import os
import joblib
import pandas as pd
import numpy as np
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import requests
from io import StringIO

# Konfiguracja
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")  # Przez Nginx proxy
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = "weather"
INFLUX_BUCKET = "weather_data"

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_TOPIC = "weather/predictions"

# Wczytaj modele
print("📦 Loading models...")
model_temp = joblib.load('model_temperature.pkl')
model_pressure = joblib.load('model_pressure.pkl')
model_humidity = joblib.load('model_humidity.pkl')
feature_columns = joblib.load('feature_columns.pkl')
print(f"✅ Models loaded! Features: {len(feature_columns)}")

def fetch_history_from_influx(station_id, hours=48):
    """Pobierz ostatnie X godzin z InfluxDB przez Nginx"""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -{hours}h)
      |> filter(fn: (r) => r["_measurement"] == "weather_measurement")
      |> filter(fn: (r) => r["station_id"] == "{station_id}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    
    response = requests.post(
        f"{INFLUX_URL}/influxdb/api/v2/query?org={INFLUX_ORG}",
        headers={
            'Authorization': f'Token {INFLUX_TOKEN}',
            'Content-Type': 'application/vnd.flux',
            'Accept': 'application/csv'
        },
        data=query,  
    )
    print(f"  🔍 Status: {response.status_code}")
    print(f"  🔍 Response: {response.text[:200]}")

    if response.status_code != 200:
        print(f"❌ InfluxDB error: {response.status_code}")
        return None
    
    # Parse CSV
    csv_data = response.text
    lines = [l for l in csv_data.split('\n') if l and not l.startswith('#')]
    
    if len(lines) < 2:
        return None
    
    df = pd.read_csv(StringIO('\n'.join(lines)))
    
    # Extract columns
    df = df.rename(columns={'_time': 'timestamp'})
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    
    required_cols = ['timestamp', 'temperature', 'pressure', 'humidity', 'wind_speed', 'wind_direction']
    df = df[required_cols].dropna()
    
    return df

def prepare_features(df_history):
    """Uproszczone feature engineering (kluczowe cechy)"""
    df = df_history.copy()
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    latest = df.iloc[-1:].copy()
    
    # Cechy czasowe
    latest['hour'] = latest['timestamp'].dt.hour
    latest['day'] = latest['timestamp'].dt.day
    latest['month'] = latest['timestamp'].dt.month
    latest['day_of_week'] = latest['timestamp'].dt.dayofweek
    latest['day_of_year'] = latest['timestamp'].dt.dayofyear
    latest['week_of_year'] = latest['timestamp'].dt.isocalendar().week.astype(int)
    latest['hour_sin'] = np.sin(2 * np.pi * latest['hour'] / 24)
    latest['hour_cos'] = np.cos(2 * np.pi * latest['hour'] / 24)
    latest['month_sin'] = np.sin(2 * np.pi * latest['month'] / 12)
    latest['month_cos'] = np.cos(2 * np.pi * latest['month'] / 12)
    latest['is_weekend'] = (latest['day_of_week'] >= 5).astype(int)
    
    # Lagi
    lag_columns = ['temperature', 'pressure', 'humidity', 'wind_speed', 'wind_direction']
    lag_periods = [1, 3, 6, 12, 24]
    
    for col in lag_columns:
        for lag in lag_periods:
            if len(df) > lag:
                latest[f'{col}_lag_{lag}h'] = df[col].iloc[-lag-1]
            else:
                latest[f'{col}_lag_{lag}h'] = df[col].iloc[0]
    
    # Rolling stats
    rolling_windows = [3, 6, 12, 24]
    for col in lag_columns:
        for window in rolling_windows:
            window_size = min(window, len(df))
            latest[f'{col}_rolling_mean_{window}h'] = df[col].iloc[-window_size:].mean()
            latest[f'{col}_rolling_std_{window}h'] = df[col].iloc[-window_size:].std()
            latest[f'{col}_rolling_min_{window}h'] = df[col].iloc[-window_size:].min()
            latest[f'{col}_rolling_max_{window}h'] = df[col].iloc[-window_size:].max()
    
    # Trendy
    delta_periods = [1, 3, 6, 12, 24]
    for col in lag_columns:
        for period in delta_periods:
            if len(df) > period:
                latest[f'{col}_delta_{period}h'] = df[col].iloc[-1] - df[col].iloc[-period-1]
                if col != 'wind_direction':
                    prev_val = df[col].iloc[-period-1]
                    if prev_val != 0:
                        latest[f'{col}_pct_change_{period}h'] = ((df[col].iloc[-1] - prev_val) / prev_val * 100)
                    else:
                        latest[f'{col}_pct_change_{period}h'] = 0
            else:
                latest[f'{col}_delta_{period}h'] = 0
                if col != 'wind_direction':
                    latest[f'{col}_pct_change_{period}h'] = 0
    
    # Dodatkowe cechy
    temp = latest['temperature'].iloc[0]
    hum = latest['humidity'].iloc[0]
    
    a, b = 17.27, 237.7
    alpha = ((a * temp) / (b + temp)) + np.log(hum / 100.0)
    latest['dew_point'] = (b * alpha) / (a - alpha)
    latest['heat_index'] = temp + 0.5555 * (6.11 * np.exp(5417.7530 * ((1/273.16) - (1/(273.15 + temp)))) * (hum/100) - 10)
    latest['temp_dewpoint_diff'] = temp - latest['dew_point']
    
    # Wypełnij brakujące
    for col in feature_columns:
        if col not in latest.columns:
            latest[col] = 0
    
    latest = latest.replace([np.inf, -np.inf], 0).fillna(0)
    
    return latest[feature_columns]

def predict_and_publish():
    """Main loop: pobierz → przewiduj → publikuj"""
    
    # Stacje do predykcji
    stations = ['station_lawica', 'station_ac1f09fffe1e035f']
    
    # MQTT client
    client = mqtt.Client(client_id="mac_predictor")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    while True:
        for station_id in stations:
            try:
                print(f"\n🔮 [{datetime.now().strftime('%H:%M:%S')}] Predicting for {station_id}...")
                
                # 1. Pobierz historię
                history = fetch_history_from_influx(station_id, hours=48)
                
                if history is None or len(history) < 24:
                    print(f"  ⚠️  Not enough data ({len(history) if history is not None else 0} records)")
                    continue
                
                # 2. Feature engineering
                features = prepare_features(history)
                
                # 3. Predykcja
                temp_pred = float(model_temp.predict(features)[0])
                pressure_pred = float(model_pressure.predict(features)[0])
                humidity_pred = float(model_humidity.predict(features)[0])
                
                # 4. Aktualne wartości
                current_temp = float(history['temperature'].iloc[-1])
                current_pressure = float(history['pressure'].iloc[-1])
                current_humidity = float(history['humidity'].iloc[-1])
                current_time = history['timestamp'].iloc[-1]
                
                # 5. JSON payload
                payload = {
                    'station_id': station_id,
                    'timestamp': datetime.now().isoformat(),
                    'current_time': current_time.isoformat(),
                    'prediction_time': (current_time + timedelta(hours=1)).isoformat(),
                    'current': {
                        'temperature': current_temp,
                        'pressure': current_pressure,
                        'humidity': current_humidity
                    },
                    'predicted': {
                        'temperature': temp_pred,
                        'pressure': pressure_pred,
                        'humidity': humidity_pred
                    }
                }
                
                # 6. Publikuj MQTT
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                print(f"  ✅ Sent: T={temp_pred:.2f}°C, P={pressure_pred:.2f}hPa, H={humidity_pred:.2f}%")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        # Czekaj 5 minut
        print(f"\n⏳ Sleeping 5 minutes...")
        time.sleep(300)

if __name__ == '__main__':
    print("🚀 Mac ML Predictor → MQTT Publisher")
    print(f"📡 InfluxDB: {INFLUX_URL}")
    print(f"📨 MQTT: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📢 Topic: {MQTT_TOPIC}")
    print("="*60)
    
    predict_and_publish()