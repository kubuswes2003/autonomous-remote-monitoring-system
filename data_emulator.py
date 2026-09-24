#!/usr/bin/env python3

import os
import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime

# Konfiguracja MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_TOPIC = "weather/station/data"

# Parametry bazowe 
BASE_TEMPERATURE = 15.0  # °C
BASE_HUMIDITY = 60.0     # %
BASE_PRESSURE = 1013.0   # hPa
BASE_WIND_SPEED = 5.0    # m/s

class WeatherStation:
    def __init__(self, station_id="STATION_001"):
        self.station_id = station_id
        self.client = mqtt.Client(client_id=station_id)
        
        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
        # Zmienne dla płynnej symulacji
        self.temp_offset = 0
        self.humidity_offset = 0
        self.pressure_offset = 0
        self.wind_offset = 0
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f" Połączono z MQTT brokerem: {MQTT_BROKER}:{MQTT_PORT}")
        else:
            print(f" Błąd połączenia. Kod: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        print("Rozłączono z MQTT brokerem")
    
    def generate_weather_data(self):
        """Generuje realistyczne dane pogodowe z małymi zmianami"""
        
        # Dodaj małe losowe zmiany dla płynności danych
        self.temp_offset += random.uniform(-0.3, 0.3)
        self.humidity_offset += random.uniform(-0.5, 0.5)
        self.pressure_offset += random.uniform(-0.2, 0.2)
        self.wind_offset += random.uniform(-0.4, 0.4)
        
        # Ogranicz offsety żeby nie odbiegały za bardzo
        self.temp_offset = max(-5, min(5, self.temp_offset))
        self.humidity_offset = max(-10, min(10, self.humidity_offset))
        self.pressure_offset = max(-5, min(5, self.pressure_offset))
        self.wind_offset = max(-3, min(3, self.wind_offset))
        
        # Generuje dane
        temperature = round(BASE_TEMPERATURE + self.temp_offset, 2)
        humidity = round(max(0, min(100, BASE_HUMIDITY + self.humidity_offset)), 2)
        pressure = round(BASE_PRESSURE + self.pressure_offset, 2)
        wind_speed = round(max(0, BASE_WIND_SPEED + self.wind_offset), 2)
        wind_direction = random.randint(0, 359)  # stopnie
        
        data = {
            "station_id": self.station_id,
            "timestamp": datetime.now().isoformat(),
            "sensors": {
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction
            },
            "battery_voltage": round(random.uniform(3.6, 4.2), 2),  # Li-Ion
            "signal_strength": random.randint(-120, -50)  # RSSI
        }
        
        return data
    
    def connect(self):
        """Połącz z MQTT brokerem"""
        try:
            print(f" Łączenie z {MQTT_BROKER}:{MQTT_PORT}...")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            time.sleep(1)  # Poczekaj na połączenie
            return True
        except Exception as e:
            print(f" Błąd połączenia: {e}")
            return False
    
    def publish_data(self, data):
        """Publikuj dane na MQTT"""
        try:
            payload = json.dumps(data, indent=2)
            result = self.client.publish(MQTT_TOPIC, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f" Wysłano dane:")
                print(f"   Temperatura: {data['sensors']['temperature']}°C")
                print(f"   Wilgotność: {data['sensors']['humidity']}%")
                print(f"   Ciśnienie: {data['sensors']['pressure']} hPa")
                print(f"   Wiatr: {data['sensors']['wind_speed']} m/s")
                print(f"   Bateria: {data['battery_voltage']}V")
                print(f"   RSSI: {data['signal_strength']} dBm")
                print("-" * 50)
                return True
            else:
                print(f" Błąd publikacji: {result.rc}")
                return False
        except Exception as e:
            print(f" Błąd: {e}")
            return False
    
    def run(self, interval=10):
        """Uruchom ciągłą symulację"""
        print(f" Uruchamianie emulatora stacji pogodowej...")
        print(f" ID Stacji: {self.station_id}")
        print(f" Topic MQTT: {MQTT_TOPIC}")
        print(f" Interwał: {interval} sekund")
        print("=" * 50)
        
        if not self.connect():
            return
        
        try:
            while True:
                data = self.generate_weather_data()
                self.publish_data(data)
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n  Zatrzymywanie emulatora...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("Emulator zatrzymany")

if __name__ == "__main__":
    # ID stacji i interwał
    station = WeatherStation(station_id="WEATHER_STATION_01")
    station.run(interval=5)  # Wysyłaj co 5 sekund