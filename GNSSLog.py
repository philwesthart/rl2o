#!/Users/dickyb/Desktop/GNSS Log/venv/bin/python

#Initializes communication via BLE to the RaceBox Micro
#Logs raw data to a text file
#Logs decoded data to an SQLite DB
#Sends latest decoded data to a UDP

import asyncio
import logging
import struct
import os
import sys
import sqlite3
import socket
import subprocess
from bleak import BleakScanner, BleakClient
from datetime import datetime
from zoneinfo import ZoneInfo

#####SETUP----------------------
#filesize limiting
ROW_LIMIT = 300000
current_row_count = 0
RB_MAC = "C1:57:6B:6E:DB:82"

#retry for lost BLE connection
MAX_RETRIES = 5

#Raw logging directory, filenames
TARGET_FOLDER = os.path.join("/home/rlto/Desktop/Logs", datetime.now().strftime("%Y-%m-%d"), "GNSS")
os.makedirs(TARGET_FOLDER, exist_ok=True)
RAW_LOG_FILE = os.path.join(TARGET_FOLDER, f"({datetime.now().strftime('%H-%M-%S')}) GNSS_raw.txt")

#SQL DB
DB_FILE = os.path.join(TARGET_FOLDER, "telemetry_log.db")

#UDP settings
UDP_IP = "255.255.255.255"
UDP_PORT = 5005
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

#Setup logging
#logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("GNSSLog")
raw_data_buffer = bytearray()


#Protocol UUID Constants
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
TX_CHAR_UUID      = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
#Message frame start and data class ID
FRAME_START = b"\xB5\x62"
DATA_CLASS_ID = b"\xFF\x01" 



#############CHECK IF RB ALREADY CONNECTED---------------------------------
def is_RB_already_connected():
    try:
        cmd = f"bluetoothctl info {RB_MAC}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        if "Connected: yes" in result.stdout:
            return True
    except Exception:
        pass
    return False




#####VALIDATE CHECKSUM--------------------------------------
def verify_checksum(packet_bytes: bytes) -> bool:
    if len(packet_bytes) < 6:
        return False
    ck_a, ck_b = 0, 0
    for byte in packet_bytes[2:-2]:  #Skip headers and trailing checksum
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a == packet_bytes[-2] and ck_b == packet_bytes[-1]





########GRABS RAW DATA-------------------------------
#Takes out packets of data from the buffer
def process_buffer():
    global raw_data_buffer
    
    while len(raw_data_buffer) >= 6:
        #Find the frame start sequence
        start_idx = raw_data_buffer.find(FRAME_START)
        
        #Drop junk bytes leading up to frame start if misaligned
        if start_idx > 0:
            del raw_data_buffer[:start_idx]
            continue
        elif start_idx == -1:
            if len(raw_data_buffer) > 1:
                del raw_data_buffer[:-1]
            break
            
        #Parse payload length (Little-Endian 16-bit unsigned integer)
        payload_len = struct.unpack("<H", raw_data_buffer[4:6])[0]
        total_packet_len = 6 + payload_len + 2  #Header(6) + Payload + Checksum(2)
        
        #If full packet hasn't arrived yet, exit loop and wait for next 
        if len(raw_data_buffer) < total_packet_len:
            break
            
        packet = bytes(raw_data_buffer[:total_packet_len])
        
        if verify_checksum(packet):
            msg_class_id = packet[2:4]
            payload = packet[6:-2]
            
            if msg_class_id == DATA_CLASS_ID:
                parse_data_message(payload)  #Hand off the clean 80-byte block 
                
            del raw_data_buffer[:total_packet_len]
        else:
            #False start pattern found; delete header bytes so we can look for the next valid one
            del raw_data_buffer[:2]
            


##############APPEND DATA TO FIFO BUFFER-----------------
def notification_handler(sender, data: bytes):
    global raw_data_buffer, current_row_count

    if current_row_count < ROW_LIMIT:
        #convert to hex
        try:
            with open(RAW_LOG_FILE, "a") as f:
                f.write(data.hex() + "\n")
            current_row_count += 1
        except IOError as e:
            pass
    
    raw_data_buffer.extend(data)
    
    # Run the processing loop immediately on incoming bytes
    process_buffer()


##########SQL DATABASE SETUP-----------------
def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            itow INTEGER,
            timestamp TEXT,
            time_flags INTEGER,
            sats INTEGER,
            fix_status INTEGER,
            fix_status_flags INTEGER,
            lat REAL,
            lon REAL,
            horizontal_accuracy REAL,
            speed REAL,
            speed_accuracy REAL,
            heading REAL,
            heading_accuracy REAL,
            gx REAL,
            gy REAL,
            gz REAL,
            rx REAL,
            ry REAL,
            rz REAL
        )
    """)
    conn.commit()
    conn.close()


        

#######DECODES RAW DATA, LOGS TO SQL--------------------
def parse_data_message(payload: bytes):    
    if len(payload) != 80:
        return
    try:
        #Extract offsets per RaceBox protocol
        
        #iTOW (interval time of week)
        itow = struct.unpack("<I", payload[0:4])[0]
        
        #Offset 4: Year (UInt16)
        #Offset 6-10: Month, Day, Hour, Minute, Second (each Bytes)
        year, month, day, hour, minute, second = struct.unpack("<HBBBBB", payload[4:11])
        nanoseconds         = struct.unpack("<i", payload[16:20])[0]
        milliseconds        = max(0, min(999, int(nanoseconds / 1000000)))
        
        #Data flags
        validity_flags      = payload[11]    #bit1=1 (valid time), bit2=1 (fully resolved)
        fix_status          = payload[20]    #0 no fix, 2=2d, 3 = 3d (target)
        fix_status_flags    = payload[21]  #bit0=1 (valid fix) and bit5=1 (valid heading)
        time_flags          = payload[22]    #Time/Date flags want =7 (time valid)
        num_sat             = payload[23]   #number sats >= 8 target
        
        #lon/lat
        longitude           = struct.unpack("<i", payload[24:28])[0]/10000000.0
        latitude            = struct.unpack("<i", payload[28:32])[0]/10000000.0

        #Horizontal accuracy, in meters
        horizontal_accuracy = struct.unpack("I", payload[36:40])[0]/1000.0

        #Speed in mph
        speed               = struct.unpack("<i", payload[48:52])[0] * 0.00223694
        speed_accuracy      = struct.unpack("<I", payload[56:60])[0] * 0.00223694

        #heading, accuracy in degrees
        heading             = struct.unpack("<i", payload[52:56])[0] / 100000.0
        heading_accuracy    = struct.unpack("<I", payload[60:64])[0]/100000.0
        
        #G-forces X, Y, Z in milli-G
        gx                  = struct.unpack("<h", payload[68:70])[0] / 1000.0
        gy                  = struct.unpack("<h", payload[70:72])[0] / 1000.0
        gz                  = struct.unpack("<h", payload[72:74])[0] / 1000.0

        #Rotation X, Y, Z, in */s
        rx                  = struct.unpack("<h", payload[74:76])[0] / 32.8
        ry                  = struct.unpack("<h", payload[76:78])[0] / 32.8
        rz                  = struct.unpack("<h", payload[78:80])[0] / 32.8

        #determine whether to use GPS time, or Linux time (as backup)
        is_date_valid = bool(payload[11] & (1 << 0))
        is_time_valid = bool(payload[11] & (1 << 1))
        if is_date_valid and is_time_valid and year > 2025:
            timestamp = datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/Chicago")).strftime(f"%Y-%m-%d %H:%M:%S.{milliseconds:03d}")
            #timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}.{milliseconds:03d}"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " HOST"

        #connect and log to SQL DB
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO telemetry(
            itow, timestamp, time_flags, sats, fix_status, fix_status_flags, lat, lon, horizontal_accuracy, speed, speed_accuracy, heading, heading_accuracy, gx, gy, gz, rx, ry, rz
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            itow, timestamp, time_flags, num_sat, fix_status, fix_status_flags, latitude, longitude, horizontal_accuracy, speed, speed_accuracy, heading, heading_accuracy, gx, gy, gz, rx, ry, rz
        ))
        conn.commit()
        conn.close()

        #UDP TRANSMIT
        telemetry_packet = (
            f"{itow},{timestamp},{time_flags},{num_sat},{fix_status},{fix_status_flags},{latitude:.7f},{longitude:.7f},{horizontal_accuracy:.3f},{speed:.2f},{speed_accuracy:.2f},{heading:.1f},{heading_accuracy:.1f},{gx:+.3f},{gy:+.3f},{gz:+.3f},{rx:+.2f},{ry:+.2f},{rz:+.2f}"
        )
        #convert string payload to bytes
        try:
            udp_socket.sendto(telemetry_packet.encode('utf-8'), (UDP_IP, UDP_PORT))
        except Exception as e:
            pass
        
        #print(f"\r[SQL LOGGED] [{timestamp}] | Sats: {num_sat} | Lat: {latitude:.7f} | Lon: {longitude:.7f} | IMU Gs (X/Y/Z): {gx:+.2f}/{gy:+.2f}/{gz:+.2f}", end="", flush=True)

    except struct.error as e:
        logger.error(f"Error unpacking payload struct: {e}")
    except sqlite3.Error as e:
        logger.error(f"Database insertion failed: {e}")
    pass
    



#####################------------------------------------
async def main():
    if is_RB_already_connected():
        logger.warning("RB already connected, cleaning-up")
        subprocess.run(["bluetoothctl", "disconnect", RB_MAC], capture_output=True)
        await asyncio.sleep(1)
        
    connection_dropped = asyncio.Event()   #flags if loss of comm

    def disconnect_handler(client):
        logger.warning("GNSS connection lost")
        connection_dropped.set()    #signal loss of comm

    while True:
        target_device = None
        connection_dropped.clear()

        #Scan for devices matching the RaceBox Micro naming convention
        for attempt in range(1, MAX_RETRIES +1):       
            logger.info("Scanning for RaceBox Micro...")
            devices = await BleakScanner.discover(timeout=5.0)
            for device in devices:
                if device.name and device.name.startswith("RaceBox Micro "):
                    target_device = device
                    logger.info(f"Found target device: {device.name} [{device.address}]")
                    break
            if target_device:
                break
            if attempt < MAX_RETRIES:
                logger.warning("Device not found, retrying scan...")
                await asyncio.sleep(1)  #brief pause
        if not target_device:
            logger.error(f"No device found after {MAX_RETRIES} attempt. Retrying in 10s.")
            await asyncio.sleep(10)
            continue

        logger.info(f"Connecting to {target_device.name}...")
        try:
            async with BleakClient(target_device.address, disconnected_callback=disconnect_handler) as client:
                if client.is_connected:
                    logger.info(f"Successfully connected to {target_device.name}!")
                    #High MTU is handled native by Bleak
                    print("Initializing SQL DB...")
                    init_database()
            
                    #logger.info("Subscribing to TX Characteristic data stream...")
                    await client.start_notify(TX_CHAR_UUID, notification_handler)
                    logger.info("Stream initialized. Press Ctrl+C to stop logging.")
                    #Keep the script running to absorb the continuous stream
                    try:
                        while not connection_dropped.is_set():
                            await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"loop error: {e}")
        except (asyncio.CancelledError, KeyboardInterrupt):
            break
                        
        except Exception as e:            
            logger.error("Connection error: {e}. Attempting recovery...")
            await asyncio.sleep(3)
            logger.info("Retrying...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        subprocess.run(["bluetoothctl", "disconnect", RB_MAC], capture_output=True)    #Racebox Micro MAC address
        print("\nRB HW link severed")
        sys.exit(0)

