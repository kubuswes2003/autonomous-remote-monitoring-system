#!/usr/bin/env python3
import os
import paho.mqtt.client as mqtt
import json
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Konfiguracja MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_TOPIC = "weather/station/data"

# Konfiguracja InfluxDB
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = "weather"
INFLUX_BUCKET = "weather_data"

# Inicjalizacja klienta InfluxDB
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✓ Połączono z MQTT brokerem")
        client.subscribe(MQTT_TOPIC)
        print(f"✓ Subskrybowano: {MQTT_TOPIC}")
    else:
        print(f"✗ Błąd połączenia. Kod: {rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        
        station_id = data.get('station_id')
        sensors = data.get('sensors', {})
        
        # Pobierz wartości (mogą być None)
        temperature = sensors.get('temperature')
        humidity = sensors.get('humidity')
        pressure = sensors.get('pressure')
        wind_speed = sensors.get('wind_speed')
        wind_direction = sensors.get('wind_direction')
        battery_voltage = data.get('battery_voltage')
        signal_strength = data.get('signal_strength')
        
        # Walidacja: temperatura i wilgotność MUSZĄ być
        if temperature is None or humidity is None:
            print(f"⚠️  Pominięto {station_id} - brak wymaganych pól (temp/humidity)")
            return
        
        # Stwórz punkt danych
        point = Point("weather_measurement").tag("station_id", station_id)
        
        # Dodaj TYLKO pola które NIE są None
        point.field("temperature", float(temperature))
        point.field("humidity", float(humidity))
        
        if pressure is not None:
            point.field("pressure", float(pressure))
        
        if wind_speed is not None:
            point.field("wind_speed", float(wind_speed))
        
        if wind_direction is not None:
            point.field("wind_direction", float(wind_direction))
        
        if battery_voltage is not None:
            point.field("battery_voltage", float(battery_voltage))
        
        if signal_strength is not None:
            point.field("signal_strength", float(signal_strength))
        
        # Zapisz do InfluxDB
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        
        # Log (z obsługą None)
        pressure_str = f"{pressure}hPa" if pressure is not None else "N/A"
        print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] {station_id}: "
              f"Temp={temperature}°C, Wilg={humidity}%, Ciśn={pressure_str}")
        
    except KeyError as e:
        print(f"✗ Brak wymaganego pola: {e}")
    except Exception as e:
        print(f"✗ Błąd: {e}")
        import traceback
        traceback.print_exc()

def main():
    client = mqtt.Client(client_id="mqtt_to_influx")
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"🔄 Łączenie z MQTT: {MQTT_BROKER}:{MQTT_PORT}")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print("⏳ Oczekiwanie na dane...")
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n⏹ Zatrzymywanie...")
    except Exception as e:
        print(f"✗ Błąd: {e}")
    finally:
        client.disconnect()
        influx_client.close()
        print("✓ Zatrzymano")

if __name__ == "__main__":
    main()
