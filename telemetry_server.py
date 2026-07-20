from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import math
import time
import threading
import sys
import can
import os
import sqlite3
import datetime
import random
from queue import Queue
import usb.core
import usb.util
import signal
import struct
from contextlib import asynccontextmanager
import asyncio
from bleak import BleakScanner, BleakClient
from zoneinfo import ZoneInfo


can_bus = None
BASE_LOG_DIR = "/home/rlto/Desktop/Logs"
ID_filter = {"0040001E", "00800021", "00300036", "00B00020"}    #CAN IDs to include
SAMPLERATE = 0.1    #CAN sampling rate
db_queue = Queue()
#daq_queue = Queue()
daq_dev = None

#GNSS SETUP
#Protocol UUID Constants
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
TX_CHAR_UUID      = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
#Message frame start and data class ID
FRAME_START = b"\xB5\x62"
DATA_CLASS_ID = b"\xFF\x01"
MAX_RETRIES = 5
raw_data_buffer = bytearray()


# Initial data dictionary
telemetry_lock = threading.Lock()   #thread sync
shutdown_event = threading.Event()  #signals threads to stop processing
telemetry={
    "RPM": None,
    "MPH": None,
    "Brake_V": None,
    "APP": None,
    "GG" : None,
    "coolant_temp": None,
    "IAT": None,
    "AAT": None,
    "Battery_V": None,
    "oil_temp": None,
    "oil_press": None,
    "AFR": None,
    "trans_temp": None,
    "boost": None,
    "lat": None,
    "long": None,
    "sats": None,
    "itow": None,
    "heading": None,
    "gx": None,
    "gy": None,
    "GNSS_timestamp": None
}
t=0

###################GNSS DATA-----------------------------------
#validates checksum
def verify_checksum(packet_bytes: bytes) -> bool:
    if len(packet_bytes) < 6:
        return False
    ck_a, ck_b = 0, 0
    for byte in packet_bytes[2:-2]:  #Skip headers and trailing checksum
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a == packet_bytes[-2] and ck_b == packet_bytes[-1]

#Takes out packets of data from the buffer
def process_buffer():
    global raw_data_buffer
    
    while len(raw_data_buffer) >= 6 and not shutdown_event.is_set():
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

def gnss_notification_handler(sender, data:bytes):
#appends data
    if shutdown_event.is_set():
        return
    raw_data_buffer.extend(data)
    process_buffer()

#Decodes and logs to SQL, pushes to FastAPI
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
            timestamp = datetime.datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/Chicago")).strftime(f"%Y-%m-%d %H:%M:%S.{milliseconds:03d}")
        else:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " HOST"
        
        #update global telemetry thread
        with telemetry_lock:
            telemetry["lat"]                = latitude
            telemetry["long"]               = longitude
            telemetry["sats"]               = num_sat
            telemetry["itow"]               = itow
            telemetry["heading"]            = heading
            telemetry["gx"]                 = gx
            telemetry["gy"]                 = gy
            telemetry["GNSS_timestamp"]     = timestamp
        
        #push
        db_queue.put(("GNSS", (
            itow, timestamp, time_flags, num_sat, fix_status, fix_status_flags, latitude, longitude, horizontal_accuracy, speed, speed_accuracy, heading, heading_accuracy, gx, gy, gz, rx, ry, rz
        )))
        #print(f"\r[SQL LOGGED] [{timestamp}] | Sats: {num_sat} | Lat: {latitude:.7f} | Lon: {longitude:.7f} | IMU Gs (X/Y/Z): {gx:+.2f}/{gy:+.2f}/{gz:+.2f}", end="", flush=True)
    except struct.error as e:
        print(f"[GNSS] Error unpacking payload struct: {e}")
        

async def gnss_ble_loop():
    connection_dropped = asyncio.Event()   #flags if loss of comm

    def disconnect_handler(client):
        print("[GNSS] Connection lost")
        connection_dropped.set()    #signal loss of comm

    while not shutdown_event.is_set():
        target_device = None
        connection_dropped.clear()

        #Scan for devices matching the RaceBox Micro naming convention
        for attempt in range(1, MAX_RETRIES +1):
            if shutdown_event.is_set():
                return
            print("[GNSS] Scanning for RaceBox Micro...")
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                for device in devices:
                    if device.name and device.name.startswith("RaceBox Micro "):
                        target_device = device
                        print(f"[GNSS] Found target device: {device.name} [{device.address}]")
                        break
                if target_device:
                    break
            except Exception as e:
                print(f"[GNSS] Scan error {e}", file=sys.stderr)
                
            if not target_device and attempt < MAX_RETRIES:
                print("[GNSS] Device not found, retrying scan...")
                await asyncio.sleep(1)  #brief pause
        if not target_device:
            print(f"[GNSS] No device found after {MAX_RETRIES} attempt. Retrying in 10s.")
            await asyncio.sleep(10)
            continue

        print(f"[GNSS] Connecting to {target_device.name}...")
        try:
            async with BleakClient(target_device.address, disconnected_callback=disconnect_handler) as client:
                if client.is_connected and not shutdown_event.is_set():
                    print(f"[GNSS] Successfully connected to {target_device.name}! Stream initialized.")
                    await client.start_notify(TX_CHAR_UUID, gnss_notification_handler)
                    #print("[GNSS] Stream initialized. Press Ctrl+C to stop logging.")
                    #Keep the script running to absorb the continuous stream
                    while not connection_dropped.is_set() and not shutdown_event.is_set():
                        await asyncio.sleep(1)
                    #logger.info("Stopping notifications and disconnecting...")
                    try:
                        await client.stop_notify(TX_CHAR_UUID)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[GNSS] Connection error {e}, retrying...")
            await asyncio.sleep(3)
#--------------------------------------------------------------------


##############CAN data---------------------------------------------
def get_can_bus_data():
    # Background loop to sample messages
    print("[CAN] Reading CAN...")
    
    try:
        bus = can.interface.Bus(channel='can0', interface='socketcan')
    except Exception as e:
        print(f"[CAN] Read failed: {e}", file=sys.stderr)
        return
    
    try:
        while not shutdown_event.is_set():
            start_window = time.time()
            while (time.time() - start_window < SAMPLERATE) and not shutdown_event.is_set():
                msg = bus.recv(timeout=0.01)
                if msg is None:
                    continue
                can_id_str = f"{msg.arbitration_id:08X}"
                
                if can_id_str in ID_filter:
                    is_valid, raw_hex = CAN_process(can_id_str, msg.data)
                    if is_valid:
                        timestamp_str = datetime.datetime.fromtimestamp(msg.timestamp).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]
                        with telemetry_lock:
                            db_queue.put(("CAN", (
                                timestamp_str, 
                                can_id_str, 
                                raw_hex,
                                telemetry["coolant_temp"], 
                                telemetry["IAT"],
                                telemetry["AAT"], 
                                telemetry["Battery_V"], 
                                telemetry["MPH"],
                                telemetry["Brake_V"], 
                                telemetry["RPM"], 
                                telemetry["APP"]
                            )))
                        
            if not shutdown_event.is_set():
                if SAMPLERATE >= 0.1:   #introduces a random jitter pause to prevent signal spacing from being missed unintentionally
                    jitter = random.uniform(SAMPLERATE*0.9, SAMPLERATE *1.1)
                    time.sleep(jitter)
                else:
                    time.sleep(0.1)
    except Exception as e:
        print(f"[CAN] Rx loop failure: {e}", file=sys.stderr)
    finally:
        bus.shutdown()




def start_can_send(interface='socketcan', channel='can0'):
    # This function initiates the CAN request background loops
    global can_bus
    try:
        can_bus = can.interface.Bus(channel=channel, interface=interface)
        #print(f"[CAN] Connected to {channel}")
    except OSError as e:
        print(f"[CAN Error] Couldn't open {channel}: {e}", file=sys.stderr)
        return False
    
    t1 = threading.Thread(target=can_loop_request1, daemon=True)
    t2 = threading.Thread(target=can_loop_request2, daemon=True)
    t1.start()
    t2.start()
    print("[CAN] Background request threads spawned successfully.")
    return True
    
def send_can_request(arbitration_id, payload_hex_str):
    # This function maintains the CAN request
    global can_bus
    if not can_bus:
        return
    
    try:
        data_bytes = bytes.fromhex(payload_hex_str)
        msg = can.Message(
            arbitration_id=arbitration_id,
            data=data_bytes,
            is_extended_id=True
        )
        can_bus.send(msg)
    except Exception as e:
        print(f"[CAN] Tx failed: {e}", file=sys.stderr)
        
def can_loop_request1():
    # 10 second interval frame requests
    while not shutdown_event.is_set():
        send_can_request(0x000FFFFE, "CD7AA610D8010000") #coolant temp
        time.sleep(0.05) #breather for data request
        send_can_request(0x000FFFFE, "CD7AA610CE010000") #IAT
        time.sleep(0.05)
        send_can_request(0x000FFFFE, "CD7AA61009010000") #AAT
        time.sleep(0.05)
        send_can_request(0x000FFFFE, "CD7AA6100A010000") #battery voltage
        time.sleep(10)  
            
def can_loop_request2():
    # 50ms interval frame requests
    while not shutdown_event.is_set():
        send_can_request(0x000FFFFE, "CD7AA6100C010000") #brake position
        time.sleep(0.05)
#--------------------------------------------------------


#####################SQL DATABASE-----------------------------
def SQL_db_setup() -> str:
    #Generate logging folder, setup DB
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(BASE_LOG_DIR, current_date)
    os.makedirs(target_dir, exist_ok=True)
    db_path = os.path.join(target_dir, "Log.db")
    conn = sqlite3.connect(db_path, timeout=5)    
    #print(f"[DEBUG] SQL DB configured at: {db_path}")
    
    #initialize table
    cursor = conn.cursor()
    
    #compression pragmas
    cursor.execute("PRAGMA journal_mode = WAL;")    # writing fast, prevents thread locking
    cursor.execute("PRAGMA synchronous = NORMAL;")  #reduces disk write sync overhead
    cursor.execute("PRAGMA page_size = 4096;")  #optimizes page storage alignment
    cursor.execute("PRAGMA auto_vacuum = INCREMENTAL;") #cleans unused space to keep filesize small
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS can_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            can_id TEXT,
            raw_data TEXT,
            coolant_temp REAL,
            IAT REAL,
            AAT REAL,
            Battery_V REAL,
            MPH REAL,
            Brake_V REAL,
            RPM INTEGER,
            APP REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DAQ (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            oil_temp REAL,
            oil_pressure REAL,
            AFR REAL,
            boost_pressure REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GNSS (
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
    return db_path

def db_worker(db_path: str):
    # Write CAN/DAQ/GNSS log to SQL
    conn = sqlite3.connect(db_path, timeout=5)
    cursor = conn.cursor()
    row_count = 0
    while not shutdown_event.is_set() or not db_queue.empty():
        try:
            item = db_queue.get(timeout=0.5)
        except:
            continue
        if item is None:    #STOP signal received
            db_queue.task_done()
            break
        
        data_type, data_payload = item
        
        if data_type == "CAN":
            cursor.execute("""
                INSERT INTO can_history
                (timestamp, can_id, raw_data, coolant_temp, IAT, AAT, Battery_V, MPH, Brake_V, RPM, APP)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data_payload)
        elif data_type =="DAQ":
            cursor.execute("""
                INSERT INTO DAQ
                (timestamp, oil_temp, oil_pressure, AFR, boost_pressure)
                VALUES (?, ?, ?, ?, ?)
            """, data_payload)
        elif data_type == "GNSS":
            cursor.execute("""INSERT INTO GNSS(
                itow, timestamp, time_flags, sats, fix_status, fix_status_flags, lat, lon, horizontal_accuracy, speed, speed_accuracy, heading, heading_accuracy, gx, gy, gz, rx, ry, rz
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data_payload)
        
        row_count += 1
        if row_count % 100 == 0: #batch transactions
            conn.commit()
        db_queue.task_done()
    conn.commit()
    conn.close()
#----------------------------------------------------------
    
    
    
################CAN LOGGING AND DECODING, --------------------
def CAN_process(can_id, data_bytes):
    global telemetry
    found = False
    
    raw_str = "".join(f"{b:02X}" for b in data_bytes)
    prefix_5byte = raw_str[:10]
    
    b8 = data_bytes[3] if len(data_bytes) > 3 else 0
    b10 = data_bytes[5] if len(data_bytes) > 5 else 0
    
    with telemetry_lock:
        if prefix_5byte == "CD7AE610D8":
            telemetry["coolant_temp"] = (b10 * 0.75) - 48
            found = True
        elif prefix_5byte == "CD7AE610CE":
            telemetry["IAT"] = (b10 * 0.75) - 48
            found = True
        elif prefix_5byte == "CD7AE61009":
            telemetry["AAT"] = (b10 * 0.75) - 48
            found = True
        elif prefix_5byte == "CD7AE6100A":
            telemetry["Battery_V"] = b10 * 0.07
            found = True
        elif prefix_5byte == "CE7AE6100C":
            if len(data_bytes) >= 7:
                combined_brake = (data_bytes[5] << 8) | data_bytes[6]
                telemetry["Brake_V"] = (combined_brake & 0x03FF) * 5 / 1024
                found = True
        if can_id == "00300036" and len(data_bytes) >= 8:
            combined_speed = (data_bytes[6] << 8) | data_bytes[7]
            telemetry["MPH"] = (combined_speed / 100) * 0.621
            found = True
        elif can_id == "0040001E" and len(data_bytes) >= 8:
            combined_rpm = (data_bytes[6] << 8) | data_bytes[7]
            telemetry["RPM"] = (combined_rpm - 57344) if combined_rpm > 57344 else 0
            APP_min, APP_max = 23, 227 #measured empirically
            telemetry["APP"] = ((b8 - APP_min) / (APP_max - APP_min)) * 100
            found = True
    return found, raw_str
#-----------------------------------------------------------




########DAQ-----------------------------------------------
def send_cmd(cmd):
    endpoint_out = 0x01
    endpoint_in = 0x81
    full_cmd = cmd + '\r'
    try:
        daq_dev.write(endpoint_out, full_cmd.encode('ascii'))
        res = daq_dev.read(endpoint_in, 16, 200) #16bytes, 200ms timeout
        return ''.join([chr(x) for x in res]).strip()
    except usb.core.USBError:
        return None

def DAQ_listener_loop():
    # setup DAQ, processes/decodes, and pushes to logging
    global daq_dev, telemetry
    endpoint_out = 0x01
    endpoint_in = 0x81
    sample_rate = 30        #in Hz, per channel
    total_channels = 4      
    
    # discover DI-2008
    try:
        daq_dev = usb.core.find(idVendor = 0x0683, idProduct=0x2008)
        if daq_dev is None:
            print("[DAQ] Device not found.", file=sys.stderr)
            return
        if daq_dev.is_kernel_driver_active(0):
            daq_dev.detach_kernel_driver(0)
        daq_dev.set_configuration()
    except Exception as e:
        print(f"[DAQ] Failed to initialize: {e}", file=sys.stderr)
        return
    
    #Initialize DAQ
    send_cmd('stop') #in case device was left scanning
    send_cmd('slist 0 4864')    #channel 1, type K TC oil temp
    send_cmd('slist 1 2817')    #16 (The Byte Count): This is the exact number of bytes you are asking Python to grab from the buffer. You are telling it, "Do not return until you have exactly 16 bytes."#channel 2, +-5V oil pressure
    send_cmd('slist 2 2818')    #channel 3, +-5V AFR
    #send_cmd('slist 3 4867')    #channel 4, type K TC trans temp
    send_cmd('slist 3 2820')    #channel 5, +-5V boost pressure
    srate = round(800 / (sample_rate*total_channels) / 4)  #calculate sample rate
    srate = max(4, min(2232, srate)) #within the bounds of what DI2008 allows
    send_cmd(f'srate {srate}')        #sample (Hz) = 800/(srate*dec)/#channels
    send_cmd('dec 4')           #samples for each reading, reduces noise
    send_cmd('filter * 1')      #average acquisition mode
    send_cmd('ps 0')            #allows for 16-byte packets
    try:
        daq_dev.read(endpoint_in, 1024, 100) #16 bytes, 100ms timeout
    except:
        pass   
    print("[DAQ] Config complete.")
    
    try:
        send_cmd('start 0')
        while not shutdown_event.is_set():
            try:
                raw_data = daq_dev.read(endpoint_in, 16, int(5*1000/sample_rate))  #16 byte packet, 5s timeout
                logtime = time.time()   #immediately log when the data was sampled
                formatted_time = datetime.datetime.fromtimestamp(logtime).strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
                #print(f"{formatted_time}")
                
                if len(raw_data) < 8:   #most likely ctrl+c
                    print(f"\n[DAQ] Warning: expecting >= 8by packet; rec'd {len(raw_data)} by")
                    try:
                        daq_dev.read(endpoint_in,1024, 50)
                    except Exception:
                        pass
                    continue
                    
                #unpack 2 signed from 16byte sample
                ch1_counts, ch2_counts, ch3_counts, ch5_counts = struct.unpack('<hhhh', raw_data[:8]) #only unpack the given 8 bytes
                #print(f"Ch1: {ch1_counts}\nCh2: {ch2_counts}\nCh3: {ch3_counts}\nCh5: {ch5_counts}")
                with telemetry_lock:    
                    #CHANNEL 1: OIL TEMP THERMOCOUPLE
                    if ch1_counts == 32767:
                        oil_temp = None
                        print("\n[DAQ] CJC Error on oil_temp")
                    elif ch1_counts == -32768:
                        oil_temp = None
                        print("\n[DAQ] TC Open Error on oil_temp")
                    else:
                        oil_temp = (0.023987 * ch1_counts) + 586
                    #print(f"{oil_temp}")
                    telemetry["oil_temp"] = oil_temp
                            
                    #CHANNEL 2: OIL PRESSURE TRANSDUCER
                    oil_pressureV = 5 * (ch2_counts / 32768) #raw voltage
                    oil_pressure = (oil_pressureV - 0.5) * 36.25
                    oil_pressure = max(0, oil_pressure) #floor
                    #print(f"2 Oil V: {oil_pressureV}")
                    telemetry["oil_press"] = oil_pressure
                        
                    #CHANNEL 3: AFR
                    afrV = 5 * (ch3_counts / 32768) #raw voltage
                    #print(f"3 AFR V: {afrV}")
                    afr = (afrV * 2) + 10 -0.2  #6/12/2026 idle shows consistent 0.2 higher than gauge
                    afr = max(10.0, min(20.0, afr)) #floor/ceiling
                    telemetry["AFR"] = afr
                            
                    #CHANNEL 4: TRANSMISSION TEMP
                    #if ch4_counts == 32767:
                    #    trans_temp = None
                    #    print("\n[DAQ] CJC Error on trans_temp")
                    #elif ch4_counts == -32768:
                    #    trans_temp = None
                    #    print("\n[DAQ] TC Open Error on trans_temp")
                    #else:
                    #    #degC = 0.023987 * counts + 586
                    #    trans_temp = (0.023987 * ch4_counts) + 586
                    #print(f"{trans_temp}")
                        
                    #CHANNEL 5: BOOST PRESSURE
                    boost_pressureV = 5 * (ch5_counts / 32768) #raw voltage
                    boost_pressure = (12.5 * boost_pressureV) - 20.95 #PSI
                    boost_pressure = max(-14.7, min(35.3, boost_pressure)) #floor/ceiling
                    #in-Hg for vac
                    if boost_pressure < 0:
                        boost_pressure = boost_pressure*2.03602
                    #print(f"5 Boost: {boost_pressureV}")                    
                    telemetry["boost"] = boost_pressure
                    
                db_queue.put(("DAQ", (formatted_time, oil_temp, oil_pressure, afr, boost_pressure)))   
                
                #print(f"[{formatted_time}] Oil temp: {oil_temp} C | Oil pressure: {oil_pressure:.2f} | AFR: {afr:.2f} | Boost pressure: {boost_pressure:.2f}")
                                        
            ###IF ERROR OCCURS IN DAQ (buffer overflow is what I've been seeing)
            except usb.core.USBError as e:
                #if shutdown
                if shutdown_event.is_set():
                    break
                    
                #if overflow (75) or timeout (110), restart DAQ
                if e.errno in [75, 110]:
                    print(f"\n[DAQ] {e.strerror} restarting DAQ script...")
                    send_cmd('stop')
                    time.sleep(3)
                    send_cmd('start 0')
                else:   #other critical errors
                    raise e
    except Exception as e:
        print(f"[DAQ] Critical failure: {e}", file=sys.stderr)
    finally:
        send_cmd('stop')
#---------------------------------------------------------------




@asynccontextmanager
async def lifespan(app: FastAPI):
    #lifespan handler for FastAPI
    
    #initialize CAN, DAQ
    shutdown_event.clear()
    print("[SQL] Configuring DB...")
    db_path = SQL_db_setup()
    
    # CAN request background process
    print("[CAN] Initializing CAN send background...")
    can_success = start_can_send(channel='can0')
    if not can_success:
        print("[CAN] Warning: Server running w/o CAN requests.")
    
    # Start background SQL logger and sampling loop
    db_thread = threading.Thread(target=db_worker, args=(db_path,), daemon=True)
    db_thread.start()
    #CAN Rx
    rx_thread = threading.Thread(target=get_can_bus_data, daemon=True)
    rx_thread.start()
    print("[CAN] Background loops running.")
    #DAQ Rx
    daq_rx_thread = threading.Thread(target=DAQ_listener_loop, daemon=True)
    daq_rx_thread.start()
    print("[DAQ] Background loops running.")
    #GNSS
    gnss_task = asyncio.create_task(gnss_ble_loop())
    print("[GNSS] Background loops running.")
    
    yield
    
    # Shutdown cleanup
    print("\nShutdown initiated, stopping loops...")
    shutdown_event.set()
    gnss_task.cancel()
    try:
        await gnss_task
    except asyncio.CancelledError:
        pass
        
    if daq_dev:
        try:
            daq_dev.write(0x01, "stop\r".encode('ascii'))
        except Exception as e:
            print(f"[DAQ] Error shutting down: {e}")
    db_queue.put(None)
    db_thread.join(timeout=3)
    print("Clean exit achieved.")
    
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    #ensure OBS CEF can access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/telemetry")
def get_data():
    #global telemetry
    global t
    t = t+1

    #return telemetry
    with telemetry_lock:
        return dict(telemetry)

app.mount("/", StaticFiles(directory="static", html=True), name="static")




#def server_shutdown_handler(signum, frame):
#    print("\nInitiating shutdown...")
#    if daq_dev:
#        try:
#            daq_dev.write(0x01, "stop\r".encode('ascii'))
#        except Exception:
#            pass
#    sys.exit(0)
#signal.signal(signal.SIGTERM,  server_shutdown_handler)
#signal.signal(signal.SIGINT, server_shutdown_handler)daq_dev.write(0x01, "stop\r".encode('ascii'))
