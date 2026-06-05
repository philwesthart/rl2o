#!/home/rlto/Desktop/Logs/Scripts/DAQ/venv/bin/python

#This script reads and logs the DAQ outputs to a raw file

import usb.core
import usb.util
import sys
import struct
import signal #captures killsw-1.sh signal
import time
import os
from datetime import datetime

#DAQ SETUP------------------------------------------
#CONFIG
sample_rate = 30        #in Hz, per channel
total_channels = 4      
row_limit = 10000       #logfile max rows

#discover DI2008
dev = usb.core.find(idVendor=0x0683, idProduct=0x2008)
dev.set_configuration()

endpoint_out = 0x01
endpoint_in = 0x81

def send_cmd(cmd):
	full_cmd = cmd + '\r'
	dev.write(endpoint_out, full_cmd.encode('ascii'))
	
	#RESPONSE
	try:
		res = dev.read(endpoint_in, 16, 200) #16bytes, 200ms timeout
		#print(f"CMD: '{cmd}'") #Protocol command
		#print(f"Hex: {bytes(res).hex(' ')}")
		#decoded_text = ''.join([chr(x) for x in res]).strip()
		#print(f"Res: '{decoded_text}'") #Protocol response
		return ''.join([chr(x) for x in res]).strip()
	except usb.core.USBError:
		return None

#SHUTDOWN INITIATED---------------------------
def shutdown_handler(signum, frame):
    print(f"\nSignal {signum} recd. Sending STOP to DI-2008...")
    try:
        dev.write(0x01, "stop\r".encode('ascii'))
        print("Stop confirmed.")
    except Exception as e:
        print(f"Shutdown error: {e}")
    finally:
        sys.exit(0)
signal.signal(signal.SIGTERM, shutdown_handler) #SIGTERM is what I'm expecting from the pkill killsw-1.sh script



#CREATE LOGFILE-------------------------------
def create_new_logfile():
    full_dir_path = os.path.join("/home/rlto/Desktop/Logs", datetime.now().strftime("%Y-%m-%d"), "DAQ")
    os.makedirs(full_dir_path, exist_ok=True) #make directory if it doesn't exist
    log_file = os.path.join(full_dir_path, datetime.now().strftime("(%H-%M-%S) DAQ.log"))
    print(f"Logging to: {log_file}")
    return os.path.join(full_dir_path, log_file) 

#DAQ CONFIGURATION SEQUENCE----------------------
send_cmd('stop')            #in case device was left scanning
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

#CALIBRATE CJC ---------------------------------this code doesn't actually work it needs debugging
#send_cmd ('cjcdelta 0 23471')
#cjc = send_cmd('cjcdelta -1')
#print(f"Internal CJC initial: {cjc}")
#response = send_cmd('adj 0')
#print(f"HW response {response}")
#import time
#time.sleep(1)

#clear old data
try:
    dev.read(endpoint_in, 1024, 100) #16 bytes, 100ms timeout
except:
    pass
    
#LOG DATA-------------------------------------------
try:
    send_cmd('start 0')
    while True:
        current_log_file = create_new_logfile()
        row_count = 0

        with open(current_log_file, "a") as f:
            f.write(f" Timestamp              OILC   OPS  AFR   BOOST\n")
            #f.write(f" -----------------------------------------------\n")
            #print(f"Logging at {sample_rate} Hz per channel...")

            while row_count < row_limit:
                try:
                    raw_data = dev.read(endpoint_in, 16, int(5*1000/sample_rate))  #16 byte packet, 5s timeout
                    logtime = time.time()   #immediately log when the data was sampled
                    formatted_time = datetime.fromtimestamp(logtime).strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
                    #print(f"{formatted_time}")
                    
                    #unpack 2 signed from 16byte sample
                    ch1_counts, ch2_counts, ch3_counts, ch5_counts = struct.unpack('<hhhh', raw_data[:8]) #only unpack the given 8 bytes
                    #print(f"Ch1: {ch1_counts}\nCh2: {ch2_counts}\nCh3: {ch3_counts}\nCh5: {ch5_counts}")
                    
                    #CHANNEL 1: OIL TEMP THERMOCOUPLE
                    if ch1_counts == 32767:
                        oil_temp = "CJC ERROR"
                    elif ch1_counts == -32768:
                        oil_temp = "TC OPEN ERROR"
                    else:
                        #print(f"1 TC cts: {ch1_counts}")
                        #oil_temp = f"{(0.023987 * ch1_counts) + 599:.2f}" #was +586 for some reason?
                        oil_temp = f"{(0.023987 * ch1_counts) + 586:.2f}"
                    #print(f"{oil_temp}")
                        
                    #CHANNEL 2: OIL PRESSURE TRANSDUCER
                    oil_pressureV = 5 * (ch2_counts / 32768) #raw voltage
                    oil_pressure = (oil_pressureV - 0.5) * 36.25
                    oil_pressure = max(0, oil_pressure) #floor
                    #print(f"2 Oil V: {oil_pressureV}")
                    
                    #CHANNEL 3: AFR
                    afrV = 5 * (ch3_counts / 32768) #raw voltage
                    #print(f"3 AFR V: {afrV}")
                    afr = (afrV * 2) + 10
                    afr = max(10.0, min(20.0, afr)) #floor/ceiling
                        
                    #CHANNEL 4: TRANSMISSION TEMP
                    #if ch4_counts == 32767:
                    #    trans_temp = "CJC ERROR"
                    #elif ch4_counts == -32768:
                    #    trans_temp = "TC OPEN ERROR"
                    #else:
                    #    #degC = 0.023987 * counts + 586
                    #    trans_temp = f"{(0.023987 * ch4_counts) + 586:.2f}"
                    #print(f"{trans_temp}")
                    
                    #CHANNEL 5: BOOST PRESSURE
                    boost_pressureV = 5 * (ch5_counts / 32768) #raw voltage
                    boost_pressure = (12.5 * boost_pressureV) - 20.95 #PSI
                    boost_pressure = max(-14.7, min(35.3, boost_pressure)) #floor/ceiling
                    #in-Hg for vac
                    if boost_pressure < 0:
                        boost_pressure = boost_pressure*2.03602
                    #print(f"5 Boost: {boost_pressureV}")
                    
                    log_entry = f"{formatted_time} {oil_temp} {oil_pressure:.2f} {afr:.2f} {boost_pressure:.2f}\n"
                    f.write(log_entry)
                    f.flush()
                    os.fsync(f.fileno())
                
                    #print(f"[{formatted_time}] Oil temp: {oil_temp} C | Oil pressure: {oil_pressure:.2f} | AFR: {afr:.2f} | Boost pressure: {boost_pressure:.2f}")
                        
                    row_count += 1
                
                ###IF ERROR OCCURS IN DAQ (buffer overflow is what I've been seeing)
                except usb.core.USBError as e:
                    #if overflow (75) or timeout (110), restart DAQ
                    if e.errno in [75, 110]:
                        print(f"\n{e.strerror} restarting DAQ script...")
                        f.close()
                        os.execv(sys.executable, [sys.executable] + sys.argv)
                    else:   #other critical errors
                        raise e
            
except KeyboardInterrupt:
    send_cmd('stop')
    print("\nLogging stopped.")
