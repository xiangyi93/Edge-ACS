#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
import time
import pymysql
from periphery import GPIO
from mcrf import MFRC522

DB_CONFIG = {
    "host": "rfid.cvqqawi4cgns.us-east-1.rds.amazonaws.com",
    "user": "admin",
    "password": "",
    "database": "rfid_access",
    "charset": "utf8mb4",
    "connect_timeout": 10
}

LED_PIN_NUM = 138  # Coral Dev Board Pin 18 → GPIO 138

continue_reading = True
led_pin = None

def setup_gpio():
    global led_pin
    try:
        led_pin = GPIO(LED_PIN_NUM, "out")
        led_pin.write(False)
        print("✅ LED GPIO initialized successfully.")
    except Exception as e:
        print("❌ Failed to initialize LED GPIO:", e)
        led_pin = None

def blink_led(times=3, on_time=0.2, off_time=0.2):
    if not led_pin:
        return
    for _ in range(times):
        led_pin.write(True)
        time.sleep(on_time)
        led_pin.write(False)
        time.sleep(off_time)

def grant_access():
    if led_pin:
        led_pin.write(True)
        time.sleep(2)
        led_pin.write(False)
        print("✅ Access granted LED signal completed.")

def get_db_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        print("✅ Successfully connected to AWS RDS MySQL database.")
        return conn
    except Exception as e:
        print("❌ Database connection failed:", e)
        return None

def log_access(uid_str, is_authorized):
    conn = get_db_connection()
    if not conn:
        print("⚠️  Skipped logging access due to DB connection issue.")
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO access_logs (uid, is_authorized) VALUES (%s, %s)",
                (uid_str, is_authorized)
            )
            conn.commit()
        print(f"✅ Successfully logged access for UID: {uid_str} (authorized: {is_authorized})")
    except Exception as e:
        print("❌ Failed to log access:", e)
    finally:
        conn.close()

def is_authorized(uid_str):
    conn = get_db_connection()
    if not conn:
        print("⚠️  Unable to verify authorization (DB down). Treating as unauthorized.")
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM rfid_users WHERE uid = %s", (uid_str,))
            row = cursor.fetchone()
            if row:
                print(f"✅ UID {uid_str} is authorized (user: {row[0]})")
                return True
            else:
                print(f"ℹ️  UID {uid_str} is NOT found in authorized_users.")
                return False
    except Exception as e:
        print("❌ Database query error during authorization check:", e)
        return False
    finally:
        conn.close()

def handle_unauthorized(uid_str):
    conn = get_db_connection()
    if not conn:
        print("⚠️  Cannot update error count (DB unavailable).")
        return 0
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO unknown_rfid (uid) VALUES (%s)", (uid_str,))
             
            conn.commit()
            
    except Exception as e:
        print("❌ Error updating unauthorized card record:", e)
        return 0
    finally:
        conn.close()

def end_read(signal, frame):
    global continue_reading, led_pin
    print("\n🛑 Ctrl+C captured, cleaning up...")
    continue_reading = False
    if led_pin:
        led_pin.write(False)
        led_pin.close()
        print("✅ LED GPIO closed cleanly.")

signal.signal(signal.SIGINT, end_read)

def main():
    global continue_reading

    print("🚀 Starting RFID Access Control System...")
    
    setup_gpio()
    
    try:
        MIFAREReader = MFRC522()
        print("✅ MFRC522 RFID reader initialized successfully.")
    except Exception as e:
        print("❌ Failed to initialize MFRC522:", e)
        return

    _ = get_db_connection()  

    print("🟢 System is ready! Scanning for RFID cards...\n")

    while continue_reading:
        (status, TagType) = MIFAREReader.Request(MIFAREReader.PICC_REQIDL)

        if status == MIFAREReader.MI_OK:
            (status, uid) = MIFAREReader.Anticoll()
            if status == MIFAREReader.MI_OK:
                uid_str = ",".join(str(x) for x in uid[:5])
                print(f"📥 Card scanned: {uid_str}")

                if is_authorized(uid_str):
                    print("🔓 ACCESS GRANTED!")
                    grant_access()
                    log_access(uid_str, True)
                else:
                    print("🚫 ACCESS DENIED")
                    log_access(uid_str, False)

                MIFAREReader.StopCrypto1()
                print("✅ Card communication ended cleanly.\n")
            else:
                print("⚠️  Anticoll() failed – retrying...")

        time.sleep(0.2)

    print("✅ Program terminated gracefully.")

if __name__ == "__main__":
    main()