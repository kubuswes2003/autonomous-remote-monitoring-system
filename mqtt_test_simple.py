#!/usr/bin/env python3
import os
import paho.mqtt.client as mqtt
import json
import base64
from datetime import datetime
from collections import defaultdict

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = 1883
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = "application/848a1f13-a778-479b-a212-1259aaab662b/device/ac1f09fffe1e035f/event/up"

# Statystyki
message_count = 0
packet_stats = defaultdict(lambda: {"count": 0, "last_seen": None, "fPort": None})
start_time = datetime.now()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ POŁĄCZONO!")
        client.subscribe(MQTT_TOPIC)
        print(f"📡 Nasłuchiwanie na: {MQTT_TOPIC}")
        print("\n" + "="*70)
        print("⏳ CZEKAM NA DANE...")
        print(f"🕐 Start: {start_time.strftime('%H:%M:%S')}")
        print("="*70 + "\n")
    else:
        print(f"❌ Błąd połączenia: {rc}")

def on_message(client, userdata, msg):
    global message_count
    message_count += 1
    
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        
        # Dekoduj payload
        if 'data' in data:
            payload_b64 = data['data']
            payload_bytes = base64.b64decode(payload_b64)
            payload_hex = payload_bytes.hex().upper()
            packet_type = payload_hex[0:2] if len(payload_hex) >= 2 else "??"
        else:
            packet_type = "NO_DATA"
            payload_hex = ""
        
        # fPort
        fPort = data.get('fPort', '?')
        
        # Zapisz statystyki
        now = datetime.now()
        packet_stats[packet_type]["count"] += 1
        packet_stats[packet_type]["fPort"] = fPort
        
        last_seen = packet_stats[packet_type]["last_seen"]
        if last_seen:
            interval = (now - last_seen).total_seconds()
        else:
            interval = None
        
        packet_stats[packet_type]["last_seen"] = now
        
        # Wyświetl
        print(f"\n📨 [{now.strftime('%H:%M:%S')}] Wiadomość #{message_count}")
        print(f"   📦 Packet Type: 0x{packet_type}")
        print(f"   🔌 fPort: {fPort}")
        print(f"   📏 Payload: {payload_hex}")
        
        if interval:
            print(f"   ⏱️  Interval: {interval:.0f}s od ostatniego 0x{packet_type}")
        
        # Pokaż statystyki co 10 wiadomości
        if message_count % 10 == 0:
            print("\n" + "="*70)
            print("📊 STATYSTYKI:")
            for ptype, stats in sorted(packet_stats.items()):
                print(f"   0x{ptype}: {stats['count']}x (fPort {stats['fPort']})")
            
            elapsed = (now - start_time).total_seconds()
            print(f"\n⏱️  Czas działania: {elapsed/60:.1f} min")
            print("="*70)
        
    except Exception as e:
        print(f"❌ Błąd: {e}")

def main():
    print("🔍 MQTT MONITOR - Statystyki pakietów")
    print(f"🌐 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"👤 User: {MQTT_USERNAME}")
    print("\nNaciśnij Ctrl+C aby zatrzymać\n")
    
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n⛔ STOP")
        
        # Pokaż końcowe statystyki
        print("\n" + "="*70)
        print("📊 KOŃCOWE STATYSTYKI:")
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"⏱️  Czas działania: {elapsed/60:.1f} min")
        print(f"📨 Całkowita liczba wiadomości: {message_count}")
        print("\nPakiety:")
        
        for ptype, stats in sorted(packet_stats.items()):
            freq = elapsed / stats['count'] if stats['count'] > 0 else 0
            print(f"   0x{ptype}: {stats['count']:3d}x (fPort {stats['fPort']}) → co {freq/60:.1f} min")
        
        print("="*70)
    except Exception as e:
        print(f"\n❌ BŁĄD: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
