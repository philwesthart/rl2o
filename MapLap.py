#!/Users/dickyb/Desktop/GNSS Log/venv/bin/python

#Loads a user-specified track map and processes it for tracking
#Receives UDP data from GNSSLog
#1) Displays a marker for the vehicle location on the map
#2) Current lap time elapsed
#3) Delta between current lap time vs. A) target or B) best
#4) Tracks best lap time
#5) Total current driver elapsed time (resetable)
#6) Total current laps current driver (resetable)
#7) Total current laps (all drivers) (separate reset)
#8) GG graph

import yaml
import socket
import os
import sys
import signal
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from pyproj import Proj, Transformer
from pathlib import Path
from matplotlib.markers import MarkerStyle
from datetime import datetime

##########SETUPS--------------------
trackdat = "Shadycrest.yml" #track map to load
track_img_name = "Shadycrest.png"   #image of track map
target_lap_time = None  #if using best, set to None




######Load track map file---------------------------
def load_yaml_data(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

###########Transforms lat/lon (WGS84) to local Transverse Mercator projection about the origin
def get_coordinate_transformer(origin_lat, origin_lon):
    local_proj = Proj(proj='tmerc', lat_0=origin_lat, lon_0=origin_lon, datum='WGS84', units='m')
    wgs84 = Proj(proj='latlong', datum='WGS84') 
    return Transformer.from_proj(wgs84, local_proj, always_xy=True)

def lla_to_xy(lat, lon, transformer):
    x, y = transformer.transform(lon, lat)
    return round(x, 3), round(y, 3)


#########Check if marker has crossed a provided gate---------------
#This is done by looking for a sign change
def check_gate_crossing(p1, p2, prev_pos, curr_pos):
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    return ccw(prev_pos, curr_pos, p1) != ccw(prev_pos, curr_pos, p2) and \
        ccw(prev_pos, p1, p2) != ccw(curr_pos, p1, p2)




######exit handler----------------
#bypass plotting loops to shutdown terminal
def universal_exit_handler(signum, frame):
    print("\nMapLap terminated by user.")
    os._exit(0)



    
###################Main---------------------------------
def main():
    global target_lap_time

    #intercept Ctrl+C at OS level
    signal.signal(signal.SIGINT, universal_exit_handler)
    
    #Load YaML track map
    script_dir = Path(__file__).resolve().parent    #where this script is saved
    yaml_path = script_dir / "Trackdat" / trackdat
    print(f"Loading track data: {yaml_path.name}...")
    data = load_yaml_data(yaml_path)

    #Origin
    origin_lat = data['origin']['lat']
    origin_lon = data['origin']['lon']
    transformer = get_coordinate_transformer(origin_lat, origin_lon)
    processed_data = {
        "name": data.get("name", "Unknown"),"units": "meters","origin": {"lat": origin_lat, "lon": origin_lon, "x": 0.0, "y": 0.0}
    }

    #start/finish
    sf = data['start_finish']
    sf_p1_x, sf_p1_y = lla_to_xy(sf['p1'][0], sf['p1'][1], transformer) #distance from origin
    sf_p2_x, sf_p2_y = lla_to_xy(sf['p2'][0], sf['p2'][1], transformer) #distance from origin
    processed_data['start_finish'] = {
        'p1': {'lat': sf['p1'][0], 'lon': sf['p1'][1], 'x': sf_p1_x, 'y': sf_p1_y},'p2': {'lat': sf['p2'][0], 'lon': sf['p2'][1], 'x': sf_p2_x, 'y': sf_p2_y}
    }

    #Sectors
    processed_data['sectors'] = []
    for sector in data.get('sectors', []):
        p1_x, p1_y = lla_to_xy(sector['p1'][0], sector['p1'][1], transformer)
        p2_x, p2_y = lla_to_xy(sector['p2'][0], sector['p2'][1], transformer)
        
        processed_data['sectors'].append({
            'name': sector['name'],'p1': {'lat': sector['p1'][0], 'lon': sector['p1'][1], 'x': p1_x, 'y': p1_y},'p2': {'lat': sector['p2'][0], 'lon': sector['p2'][1], 'x': p2_x, 'y': p2_y}
        })
        
    #Reference path
    processed_data['reference_path'] = {
        'type': data['reference_path'].get('type'),'points': []
    }
    for pt in data['reference_path'].get('points', []):
        x, y = lla_to_xy(pt[0], pt[1], transformer)
        processed_data['reference_path']['points'].append({
            'lat': pt[0], 'lon': pt[1], 'x': x, 'y': y
        })

    #Debug print
    #print(f"Map: {processed_data['name']}")
    #print(f"Origin: ({origin_lat}*, {origin_lon}*)")
    
    #print("\nStart/Finish Line:")
    #print(f"  P1 -> X: {processed_data['start_finish']['p1']['x']}m, Y: {processed_data['start_finish']['p1']['y']}m")
    #print(f"  P2 -> X: {processed_data['start_finish']['p2']['x']}m, Y: {processed_data['start_finish']['p2']['y']}m")
    
    #print("\nSectors:")
    #for sector in processed_data['sectors']:
        #print(f"  {sector['name']}:")
        #print(f"    P1 -> X: {sector['p1']['x']}m, Y: {sector['p1']['y']}m")
        #print(f"    P2 -> X: {sector['p2']['x']}m, Y: {sector['p2']['y']}m")
        
    #print(f"\nReference Path {len(processed_data['reference_path']['points'])} points.")
    #print("  First 2 points sample:")
    #for pt in processed_data['reference_path']['points'][:2]:
        #print(f"    X: {pt['x']}m, Y: {pt['y']}m")

    #YAML track image info
    pixel_scale = float(data.get('pixel_scale', 1.0))   #default given at end
    pixel_extents = data.get('extents_from_origin', [-500, 500, -300, 300]) #default given at end
    map_rotation_offset = float(data.get('deg_from_N', 0.0))    #default given at end
    track_img_scale = [px * pixel_scale for px in pixel_extents]    #divide pixel boundary by scale to get scale
    #print(f"{track_img_scale[0]}, {track_img_scale[1]}, {track_img_scale[2]}, {track_img_scale[3]}")
    


    #######Setup track visualization----------------------------------------
    plt.ion()   #interactive mode
    fig, ax = plt.subplots(figsize=(10,6))

    #load track image
    img_path = script_dir / "Trackdat" / track_img_name
    if img_path.exists():
        print(f"Loading track map {img_path.name}...")
        img = mpimg.imread(str(img_path))
        ax.imshow(img, extent=track_img_scale, origin='upper')  #display image mapped to meter grid
    else:
        #set blank grid if no image found
        print(f"No track image found at {img_path}")
        ax.set_xlim(-500,500)
        ax.set_ylim(-300,300)
    #Labels and plot setup
    ax.set_title(f"Live tracking {data.get('name')}")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect('equal', adjustable='box')
    #start/finish line
    ax.plot([sf_p1_x, sf_p2_x], [sf_p1_y, sf_p2_y], color='black', linestyle='solid', linewidth=2, zorder=4)
    #sectors
    for sector in processed_data['sectors']:
        ax.plot(
            [sector['p1']['x'], sector['p2']['x']],
            [sector['p1']['y'], sector['p2']['y']],
            color='red',
            linestyle='dashed',
            linewidth=1,
            zorder=4
        )
    


    #Configure UDP port
    UDP_IP = "0.0.0.0"
    UDP_PORT = 5005
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.bind((UDP_IP, UDP_PORT))
        print(f"MapLap active. Listening on UDP {UDP_PORT}...")
    except Exception as e:
        print(f"Failed to bind to port: {e}")
        return

    ########Live data processing---------------
    try:
        #vehicle pointer setup initially at 0,0
        vehicle_pointer, = ax.plot(
            0, 0,
            marker=[(-5, -8), (0, 8), (5, -8)],
            markeredgecolor='black',
            markerfacecolor='cyan',
            markeredgewidth=1.5,
            markersize=15,
            zorder=5
        )


        #Debug text box setup
        telemetry_text = ax.text(
            0.98, 0.02, "", #bottom RH
            transform=ax.transAxes,
            fontsize=8,
            fontfamily='monospace', #keeps vertical number alignment
            verticalalignment='bottom',
            horizontalalignment='right',
            zorder=6,
            bbox=dict(boxstyle='round', pad=0.5, facecolor='black', alpha=0.7, edgecolor='none')
        )

        plt.show(block=False)

        #BLIT initial and cache
        fig.canvas.draw()
        bg_cache = fig.canvas.copy_from_bbox(ax.bbox)


        #Laptiming variables
        prev_pos = None
        lap_start_itow = None
        lap_count = 0
        last_lap_time = 0.000
        current_lap_elapsed = 0.0
        if target_lap_time == None:  #if best lap times should be used
            target_lap_time = float('inf')
            best_lap_marker = 1



        #Delta timer
        num_sectors = len(processed_data['sectors'])
        target_sector_times = [float('inf')] * num_sectors  #set a default high target sector time
        sector_crossed = [False] * num_sectors  #setup for crossing sectors
        current_delta_text = "0.00"
        
        
        while True:
            data_bytes, addr = sock.recvfrom(1024)  #1024by is overkill
            
            #due to lag issues, below is to empty backlog of old packets which queue-up
            while True:
                try:
                    data_bytes, _ = sock.recvfrom(1024, socket.MSG_DONTWAIT)
                except (BlockingIOError, OSError):
                    break   #buffer empty
                
            try:
                #Decode incoming GNSS
                payload = data_bytes.decode('utf-8').strip()
                telemetry_fields = payload.split(',')
                itow               = int(telemetry_fields[0])
                timestamp          = telemetry_fields[1] #Kept as string
                timestamp2         = timestamp[11:19]   #a version to print for debugging
                local_time         = datetime.now().strftime("%H:%M:%S")
                time_flags         = int(telemetry_fields[2])
                num_sat            = int(telemetry_fields[3])
                fix_status         = int(telemetry_fields[4])
                fix_status_flags   = int(telemetry_fields[5])
                latitude           = float(telemetry_fields[6])
                longitude          = float(telemetry_fields[7])
                horizontal_accuracy= float(telemetry_fields[8])
                speed              = float(telemetry_fields[9])
                speed_accuracy     = float(telemetry_fields[10])
                heading            = float(telemetry_fields[11])
                heading_accuracy   = float(telemetry_fields[12])
                #G-forces
                gx                 = float(telemetry_fields[13])
                gy                 = float(telemetry_fields[14])
                gz                 = float(telemetry_fields[15])
                #Rotation rates
                rx                 = float(telemetry_fields[16])
                ry                 = float(telemetry_fields[17])
                rz                 = float(telemetry_fields[18])

                #calculate vehicle pointer
                x_meters, y_meters = lla_to_xy(latitude, longitude, transformer)
                vehicle_pointer.set_data([x_meters], [y_meters])
                t = plt.matplotlib.transforms.Affine2D().rotate_deg(-heading)
                vehicle_pointer.set_marker(MarkerStyle(marker=[(-5, -8), (0, 8), (5, -8)], transform=t))

                #Debug print to Terminal
                #print(f"Time: {timestamp} | Sats: {num_sat} | Fix: {fix_status}")
                #print(f"Track pos: {x_meters:8.3f}m, {y_meters:8.3f}m")
                #print(f"Speed: {speed:5.2f} mph | Heading: {heading:5.1f}*")
                #print(f"Gx {gx:+.1f}, Gy {gy:+.1f}, Gz {gz:+.1f}")
                #print(f"Rx {rx:+.1f}, Ry {ry:+.1f}, Rz {rz:+.1f}")

                #####Lap timer----------------------------------------
                current_pos = (x_meters, y_meters)
                if prev_pos is not None:
                    #check sectors
                    if lap_start_itow is not None:
                        current_lap_elapsed = (itow - lap_start_itow) / 1000
                        for i, sector in enumerate(processed_data['sectors']):
                            #Only check if we haven't crossed this sector yet on this lap
                            if not sector_crossed[i]:
                                p1 = (sector['p1']['x'], sector['p1']['y'])
                                p2 = (sector['p2']['x'], sector['p2']['y'])
                                if check_gate_crossing(p1, p2, prev_pos, current_pos):
                                    sector_crossed[i] = True
                                    #Calculate time from S/F to this sector
                                    this_lap_sector_times[i] = current_lap_elapsed
                                    #time_to_sector = current_lap_elapsed
                    
                                    #If a valid target exists, calculate delta (Current - Target)
                                    if target_sector_times[i] != float('inf'):
                                        delta_TTS = current_lap_elapsed - target_sector_times[i]
                                        current_delta_text = f"{delta_TTS:+.2f}"
                                        print(f" Crossed {sector['name']} | Delta: {current_delta_text}") #debug
                                    else:
                                        current_delta_text = "- "


                                        
                    if check_gate_crossing((sf_p1_x, sf_p1_y), (sf_p2_x, sf_p2_y), prev_pos, current_pos):
                        #if first time crossing line (start lap timer)
                        if lap_start_itow is None:
                            print("Lap timer started...")
                            lap_start_itow = itow
                            lap_count = 0
                            this_lap_sector_times = [0.0] * num_sectors #temp variable to log current lap sectors

                        #if a subsequent lap
                        else:
                            lap_duration = (itow - lap_start_itow) / 1000
                            last_lap_time = f"{lap_duration:.3f}"                            
                            if lap_duration < target_lap_time:
                                if best_lap_marker == 1: #if =1 than best =target, if =0 then target stays
                                    target_lap_time = lap_duration
                                    target_sector_times = list(this_lap_sector_times)
                                else: #if chasing target times instead...
                                    pass
                            
                            print(f"Lap completed: {lap_count}, {last_lap_time}s | Target: {target_lap_time:.3f}s")
                            lap_count += 1
                            lap_start_itow = itow   #reset new anchor mark
                            this_lap_sector_times = [0.0] * num_sectors #reset curr lap sector timings
                            sector_crossed = [False] * num_sectors
                            
                    #Only run timer if it's already initialized
                    if lap_start_itow is not None:
                        current_lap_elapsed = (itow - lap_start_itow) / 1000
                        for i in range(num_sectors):
                            if not sector_crossed[i]:
                                this_lap_sector_times[i] = current_lap_elapsed  #record split time for sector
                    else:
                        current_lap_elapsed = 0.000
                prev_pos = current_pos
                #display best and current
                target_lap_text = f"{target_lap_time:.2f}" if target_lap_time != float('inf') else "0.000s"
    


                

                #DEBUG textbox on plot
                debug_string = (
                    f"GNSS: {timestamp2}\n"
                    f"Bee: {local_time}\n"
                    f"Sats: {num_sat}\n"
                    #f"H-Acc: {float(horizontal_accuracy):.2f}m\n"
                    #f"Hdg-Acc: {float(heading_accuracy):.1f}*\n"
                    f"\n"
                    f"Lap: {lap_count}\n"
                    f"Curr: {current_lap_elapsed:.2f} s\n"
                    f"Delta: {current_delta_text} s\n"
                    f"Last: {last_lap_time:.2f} s\n"
                    f"Target: {target_lap_text} s"
                )
                telemetry_text.set_text(debug_string)
                telemetry_text.set_color('white')



                #BLIT
                fig.canvas.restore_region(bg_cache)
                ax.draw_artist(vehicle_pointer)
                ax.draw_artist(telemetry_text)
                fig.canvas.blit(ax.bbox)
                fig.canvas.flush_events()
                
            except ValueError as ve:
                print(f"Data conversion error: {ve}")
            except Exception as e:
                print(f"Unexpected error: {e}")
    finally:
        sock.close()
                

if __name__ == "__main__":
    main()
