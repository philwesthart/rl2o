#!/home/rlto/Desktop/Logs/Scripts/venv/bin/python

#This script creates a series of generic plots from user-selected data files.
#It also allows users to generate new plots w/ specified data sets and colors.

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.animation import FuncAnimation
import collections
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import glob
from datetime import datetime

#############DATA PARSING---------------------------------
def parse_line(line):
    #parses the CAN data lines. Adjust the split character and indices
    #based on file format.
    try:
        parts = line.split()
        if len(parts) < 10: #ensure we have all columns
            return None
        
        #parts 0 is date, parts 1 is time
        timestamp = parts[1]
        
        #Mapping to file format
        CT = float(parts[2])
        IAT = float(parts[3])
        AAT = float(parts[4])
        Batt = float(parts[5])
        MPH = float(parts[6])
        Brake = float(parts[7])
        RPM = float(parts[8])
        APP = float(parts[9])
        
        return {"time": timestamp, "CT": CT, "IAT":IAT, "AAT":AAT, "Batt":Batt, "MPH": MPH, "Brake":Brake, "RPM":RPM, "APP":APP}
    except (ValueError, IndexError):
        return None
        
def parse_DAQ_line(line):
    #parses DAQ data lines
    try:
        parts = line.split()
        if len(parts) < 6:
            return None
        
        timestamp = parts[1]
        
        #Mapping to file format
        OILC = float(parts[2])
        OPS = float(parts[3])
        AFR = float(parts[4])
        BOOST = float(parts[5])
        
        return {"time":timestamp, "OILC":OILC, "OPS":OPS, "AFR":AFR, "BOOST":BOOST}
    except (ValueError, IndexError):
        return None
        
############STREAM PLOTS---------------------
def stream_plot(CAN_path, DAQ_path, CAN_buffer_size, DAQ_buffer_size, update_rate):
    fig_CAN, axes_CAN = plt.subplots(4, 1, figsize=(8, 8))
    fig_CAN.canvas.manager.set_window_title("CAN Stream")
    ax1, ax2, ax3, ax4 = axes_CAN
    mph_line, = ax1.plot([], [], lw=2, color = 'blue', label='MPH')
    rpm_line, = ax2.plot([], [], lw=2, color = 'red', label='RPM')
    brake_line, = ax3.plot([], [], lw=2, color = 'green', label='Brake')
    app_line, = ax4.plot([], [], lw=2, color = 'orange', label='APP')
    ax1.set_ylabel('MPH')
    ax2.set_ylabel('RPM')
    ax3.set_ylabel('Brake V')
    ax4.set_ylabel('APP %')
    for ax in axes_CAN: ax.legend(loc='upper left')
 

    #current stat panel
    status_text = fig_CAN.text(0.02, 0.02, "CT:-- | IAT:-- | AAT:-- | Batt:--", fontsize=12, bbox=dict(facecolor='white', alpha=0.8))
    
    #######DAQ
    fig_DAQ, axes_DAQ = plt.subplots(4, 1, figsize=(8, 8))
    fig_DAQ.canvas.manager.set_window_title("DAQ Stream")
    ax5, ax6, ax7, ax8 = axes_DAQ
    oilc_line, = ax5.plot([], [], lw=2, color = 'purple', label='Oil Temp')
    ops_line, = ax6.plot([], [] ,lw=2, color = 'cyan', label='Oil Press')
    afr_line, = ax7.plot([], [], lw=2, color = 'magenta', label='AFR')
    boost_line, = ax8.plot([], [], lw=2, color = 'black', label='Boost')
    ax5.set_ylabel('Oil *C')
    ax6.set_ylabel('Oil PSI')
    ax7.set_ylabel('AFR')
    ax8.set_ylabel('Boost inHg/psi')
    for ax in axes_DAQ: ax.legend(loc='upper left')
    
    #y-axis ranges
    ax1.set_ylim(0, 100)     #mph
    ax2.set_ylim(0, 6000)   #rpm
    ax3.set_ylim(1.5, 3.1)  #brake V
    ax4.set_ylim(0, 100)    #APP%
    ax5.set_ylim(20, 140)   #oil temp
    ax6.set_ylim(0, 60)     #oil pressure
    ax7.set_ylim(10, 20)    #afr
    ax8.set_ylim(-30, 20)   #boost
    
    #setup horizontal lines
    ax5.axhline(y=121, color='gray', linestyle='--', linewidth=1.2, zorder=1)  #oil temp 240F = 121C
    ax8.axhline(y=0, color='gray', linestyle='--', linewidth=1.2, zorder=1)
    
    #setup current value labels
    mph_text  = ax1.text(0.98, 0.92, '', transform=ax1.transAxes, ha='right', va='top', fontsize=12, color='blue')
    rpm_text  = ax2.text(0.98, 0.92, '', transform=ax2.transAxes, ha='right', va='top', fontsize=12, color='red')
    brake_text= ax3.text(0.98, 0.92, '', transform=ax3.transAxes, ha='right', va='top', fontsize=12, color='green')
    app_text  = ax4.text(0.98, 0.92, '', transform=ax4.transAxes, ha='right', va='top', fontsize=12, color='orange')
    oilc_text  = ax5.text(0.98, 0.92, '', transform=ax5.transAxes, ha='right', va='top', fontsize=12, color='purple')
    ops_text   = ax6.text(0.98, 0.92, '', transform=ax6.transAxes, ha='right', va='top', fontsize=12, color='cyan')
    afr_text   = ax7.text(0.98, 0.92, '', transform=ax7.transAxes, ha='right', va='top', fontsize=12, color='magenta')
    boost_text = ax8.text(0.98, 0.92, '', transform=ax8.transAxes, ha='right', va='top', fontsize=12, color='black')
    
    #data buffers
    x_CAN_data = collections.deque(maxlen=CAN_buffer_size)
    mph_data, rpm_data, brake_data, app_data = [collections.deque(maxlen=CAN_buffer_size) for _ in range(4)]
    x_DAQ_data = collections.deque(maxlen=DAQ_buffer_size)
    oilc_data, ops_data, afr_data,boost_data = [collections.deque(maxlen=DAQ_buffer_size) for _ in range(4)]
    
    #keep track of where read in CAN file
    f_CAN = open(CAN_path, 'r')
    f_CAN.seek(0, 2) #go to the end of the file initially
    last_pos_CAN = f_CAN.tell()
    
    f_DAQ = None
    last_pos_DAQ = 0
    if DAQ_path:
        f_DAQ = open(DAQ_path, 'r')
        f_DAQ.seek(0, 2)
        last_pos_DAQ = f_DAQ.tell()
        
    def update(frame):
        nonlocal last_pos_CAN, last_pos_DAQ
        
        #Read new CAN lines
        f_CAN.seek(last_pos_CAN)
        new_CAN_lines = f_CAN.readlines()
        last_pos_CAN = f_CAN.tell()
        latest_CAN = {}
                       
        for line in new_CAN_lines:
            data = parse_line(line)
            if data:
                x_CAN_data.append(data['time'][:8]) #HH:MM:SS
                mph_data.append(data['MPH'])
                rpm_data.append(data['RPM'])
                brake_data.append(data['Brake'])
                app_data.append(data['APP'])
                latest_CAN = data
                
        #Read new DAQ lines
        f_DAQ_lines_read = False #reset
        if f_DAQ:
            f_DAQ.seek(last_pos_DAQ)
            new_DAQ_lines = f_DAQ.readlines()
            last_pos_DAQ = f_DAQ.tell()
            if new_DAQ_lines:
                f_DAQ_lines_read = True            
                for line in new_DAQ_lines:
                    DAQ_data = parse_DAQ_line(line)
                    if DAQ_data:
                        x_DAQ_data.append(DAQ_data['time'][:8]) #HH:MM:SS
                        oilc_data.append(DAQ_data['OILC'])
                        ops_data.append(DAQ_data['OPS'])
                        afr_data.append(DAQ_data['AFR'])
                        boost_data.append(DAQ_data['BOOST'])
        
        #refresh CAN plots
        if new_CAN_lines:
            x_CAN_range = range(len(x_CAN_data))
            mph_line.set_data(x_CAN_range, mph_data)
            rpm_line.set_data(x_CAN_range, rpm_data)
            brake_line.set_data(x_CAN_range, brake_data)
            app_line.set_data(x_CAN_range, app_data)
            
            tick_ratio = 8 #dynamic x-axis labeling
            step = max(1, CAN_buffer_size // tick_ratio)
            for ax in [ax1, ax2, ax3]: ax.set_xticks([])    #block tick marks
            for ax in [ax1, ax2, ax3, ax4]: ax.relim(); ax.autoscale_view(scalex=True, scaley=False)     #rescale view
            ax4.set_xticks(x_CAN_range[::step]) #show a label every STEP points
            ax4.set_xticklabels(list(x_CAN_data)[::step], rotation=0, ha='right')
            

            #Status box and data labels, then update plot
            if latest_CAN:
                mph_text.set_text(f"{latest_CAN.get('MPH', 0):.0f}")
                rpm_text.set_text(f"{latest_CAN.get('RPM', 0):.0f}")
                brake_text.set_text(f"{latest_CAN.get('Brake', 0):.2f}")
                app_text.set_text(f"{latest_CAN.get('APP', 0):.0f}")
            
            status_text.set_text(f"CT:{latest_CAN['CT']:.0f}*C | IAT:{latest_CAN['IAT']:.0f}*C | AAT: {latest_CAN['AAT']:.0f}*C | Batt: {latest_CAN['Batt']}V")  
            fig_CAN.canvas.draw_idle()  #update CAN plot
            
            
            
            
            
        if f_DAQ_lines_read and x_DAQ_data:
            x_DAQ_range = range(len(x_DAQ_data))
            oilc_line.set_data(x_DAQ_range, oilc_data)
            ops_line.set_data(x_DAQ_range, ops_data)
            afr_line.set_data(x_DAQ_range, afr_data)
            boost_line.set_data(x_DAQ_range, boost_data)
            
            DAQ_tick_ratio = 8 #dynamic x-axis labeling specific for DAQ
            step_DAQ = max(1, DAQ_buffer_size // DAQ_tick_ratio)
            for ax in [ax5, ax6, ax7]: ax.set_xticks([])    #hides tick marks
            for ax in [ax5, ax6, ax7, ax8]: ax.relim(); ax.autoscale_view(scalex=True, scaley=False)    #rescale axes
            ax8.set_xticks(x_DAQ_range[::step_DAQ])
            ax8.set_xticklabels(list(x_DAQ_data)[::step_DAQ], rotation=0, ha='right')
            
            #data labels then update plot
            if 'DAQ_data' in locals() and DAQ_data:
                oilc_text.set_text(f"{DAQ_data.get('OILC', 0):.0f}")
                ops_text.set_text(f"{DAQ_data.get('OPS', 0):.0f}")
                afr_text.set_text(f"{DAQ_data.get('AFR', 0):.1f}")
                boost_text.set_text(f"{DAQ_data.get('BOOST', 0):.1f}")
            fig_DAQ.canvas.draw_idle()  #update DAQ plot
            
        return (mph_line, rpm_line, brake_line, app_line, status_text, oilc_line, ops_line, afr_line, boost_line, mph_text, rpm_text, brake_text, app_text, oilc_text, ops_text, afr_text, boost_text)
        
    ani = FuncAnimation(fig_CAN, update, interval=update_rate, cache_frame_data=False)
    fig_CAN.tight_layout()
    fig_DAQ.tight_layout()
    fig_CAN.subplots_adjust(bottom=0.08, hspace=0.4)
    plt.show()
    f_CAN.close()
    f_DAQ.close()

##############GET THE LATEST FILE------------------
def get_latest_log():
    today_str = datetime.now().strftime('%Y-%m-%d')
    folder_path = f"/home/rlto/Desktop/Logs/{today_str}"
    
    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return None, None
        
    def extract_time(filepath):
        filename = os.path.basename(filepath)
        filename_noext, _ = os.path.splitext(filename)
        clean_name = filename_noext.replace('(', '').replace(')','')
        try:
            parsed_time = filename_noext.split(')')[0]
            clean_name = parsed_time.replace('(','')
            return [int(x) for x in clean_name.split('-')]
        except ValueError:
            return [0, 0, 0] #fallback for non-matching files
    
    #search for CAN files
    CAN_files = glob.glob(f"{folder_path}/*.txt")
    latest_CAN_file = None
    #for i, file in enumerate(sorted(CAN_files), 1):
    #    print(f"{i}. {os.path.basename(file)}")
    if CAN_files:
        latest_CAN_file = max(CAN_files, key=extract_time)
        print(f"Loading latest log: {latest_CAN_file}")    
    else:
        print("No *.txt files found.")
    
    #Latest DAQ file
    DAQ_folder = os.path.join(folder_path, "DAQ")
    latest_DAQ_file = None
    if os.path.exists(DAQ_folder):
        DAQ_files = glob.glob(f"{DAQ_folder}/*.log")
        #for i, file in enumerate(sorted(DAQ_files), 1):
        #    print(f"{i}. {os.path.basename(file)}")
        if DAQ_files:
            #print(f"Sample DAQ: { [os.path.basename(f) for f in DAQ_files[:3]] }")
            latest_DAQ_file = max(DAQ_files, key=extract_time)
            print(f"Loading DAQ: {latest_DAQ_file}")
        else:
            print("No *.log files found.")
    else:
        print(f"DAQ folder not found: {DAQ_folder}")
        
    return latest_CAN_file, latest_DAQ_file

##############MAIN SCRIPT-------------------------------------
def main_menu():
    df=None  
    CAN_path, DAQ_path = get_latest_log()
    CAN_buffer_size = 1350
    DAQ_buffer_size = 100
    update_rate = 500 #ms
    if CAN_path:
        stream_plot(CAN_path, DAQ_path, CAN_buffer_size, DAQ_buffer_size, update_rate)            

if __name__ == "__main__":
    main_menu()
