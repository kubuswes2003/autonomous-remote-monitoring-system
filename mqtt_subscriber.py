#!/usr/bin/env python3
"""
Prosty subscriber do testowania odbierania danych z MQTT
"""

import os
import paho.mqtt.client as mqtt
import json
from datetime import datetime

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_TOPIC = "weather/station/data"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Połączono z MQTT brokerem")
        print(f"Subskrybowanie topic: {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Błąd połączenia. Kod: {rc}")

def on_message(client, userdata, msg):
    """Callback wywoływany gdy przyjdzie wiadomość"""
    try:
        data = json.loads(msg.payload.decode())
        
        print("\n" + "=" * 60)
        print(f"Otrzymano dane o {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        print(f"Stacja: {data['station_id']}")
        print(f"Timestamp: {data['timestamp']}")
        print("\n Czujniki:")
        print(f"   Temperatura:  {data['sensors']['temperature']}°C")
        print(f"   Wilgotność:    {data['sensors']['humidity']}%")
        print(f"   Ciśnienie:     {data['sensors']['pressure']} hPa")
        print(f"   Wiatr:         {data['sensors']['wind_speed']} m/s @ {data['sensors']['wind_direction']}°")
        print(f"\n Bateria:        {data['battery_voltage']}V")
        print(f" Siła sygnału:   {data['signal_strength']} dBm")
        print("-" * 60)
        
    except json.JSONDecodeError:
        print(f" Błąd dekodowania JSON: {msg.payload}")
    except Exception as e:
        print(f" Błąd: {e}")

def main():
    client = mqtt.Client(client_id="weather_subscriber")
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f" Łączenie z MQTT brokerem: {MQTT_BROKER}:{MQTT_PORT}")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(" Oczekiwanie na dane...")
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n Zatrzymywanie subscribera...")
    except Exception as e:
        print(f" Błąd: {e}")
    finally:
        client.disconnect()
        print(" Subscriber zatrzymany")

if __name__ == "__main__":
    main()