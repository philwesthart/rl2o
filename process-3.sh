#!/bin/bash

#this script looks for new CAN *.log files in the logging folder.
#when a new file is created, it streams a real-time conversion to human-readable
#format into a *.txt file.

#CONFIGURATION
LOG_DIR="/home/rlto/Desktop/Logs/$(date +%F)"
ID_FILTER="0040001E|00800021|00300036|00B00020"
ROW_LIMIT=300000	#300k originally
FIFO_PIPE="/home/rlto/Desktop/Logs/data_stream.fifo"

echo "Initializing CAN streaming on $LOG_DIR..."

#clean-up FIFO
rm -f "$FIFO_PIPE"
mkfifo "$FIFO_PIPE"

#Monitor directory
exec 3<> "$FIFO_PIPE"

#process logs initially in folder
for f in "$LOG_DIR"/*.log; do
	if [ -f "$f" ]; then
		tail -n +3 -qF "$f" >&3 2>/dev/null & #-n +3 -c +0 -qF
	fi
done
	
#monitor for new files
inotifywait -m -e create -e moved_to --format '%w%f' "$LOG_DIR" 2>/dev/null | while read -r NEW_FILE; do
	if [[ "$NEW_FILE" == *.log ]]; then
		echo "New file detected: $NEW_FILE" >&2
		tail -n +3 -qF "$NEW_FILE" >&3 2>/dev/null &
	fi
done &

#Capture background process ID to clean-up if script is stopped
MONITOR_PID=$!
trap 'pkill -P $$ 2>/dev/null; exec 3>&-; rm -f "$FIFO_PIPE"; exit' INT TERM EXIT

#Filter
awk -v fld="$ID_FILTER" -v LIMIT="$ROW_LIMIT" -v dir="$LOG_DIR" '

BEGIN {
	ROW_COUNT = 0;
	COUT = dir "/(" strftime("%H-%M-%S") ").txt"
	print "Timestamp               CT     IAT   AAT   BATT  MPH    BRKV  RPM  APP  " > COUT;
	fflush(COUT);	#write header immediately
	
	#manual loop check
	while (1) {
		#attempt to read line from pipe
		status = (getline < "/home/rlto/Desktop/Logs/data_stream.fifo");
		if (status <= 0) {
			#close pipe, pause, and restart
			close("/home/rlto/Desktop/Logs/data_stream.fifo");
			system("sleep 2");
			$0 = ""; #clear inputs
			continue;
		}
		process_line();
	}
}

####PROCESS CAN DATA------------------------------------------

function process_line() {
	if ($3 ~ fld) {	#this command filters out non-pertinent messages
		#Determine if starting a new file
		if (COUT == "" || ROW_COUNT >= LIMIT) {
			#grab the timestamp
			RAW_TIMESTAMP = $1;
			gsub(/[()]/, "", RAW_TIMESTAMP);
			split(RAW_TIMESTAMP, TIMESTAMP_PARTS, ".");	#split out ms
			FILE_TIME = strftime("%H-%M-%S", TIMESTAMP_PARTS[1]);	#convert seconds to HH-MM-SS
			if (FILE_TIME == "") {
				FILE_TIME = "unknown";
			}
			
			#close previous file buffer if active
			if (COUT != "") {
				close(COUT);
			}
			
			#write file w/ header
			COUT = dir "/(" FILE_TIME ").txt"
			ROW_COUNT = 0;
			print "Timestamp               CT     IAT   AAT   BATT  MPH    BRKV  RPM  APP  " > COUT;
		}
		#CONVERT TIMESTAMP
		gsub(/[()]/, "", $1); #remove parentheses
		split($1, PARTS, "."); #split epoch time at decimal point so we preserve fractional seconds
		FORMATTED_TIME=strftime("%Y/%m/%d %H:%M:%S", PARTS[1]);
		MILLISECONDS=substr(PARTS[2], 1, 3); #grab last 3 of split epoch time
		$1 = FORMATTED_TIME "." MILLISECONDS;
					
		#combine all data into single
		CURRENT_DATA=$5$6$7$8$9;
		FOUND=0; #reset FOUND
									
		#coolant temp
		if (CURRENT_DATA == "CD7AE610D8") {
		COOLANT_TEMP_C=(strtonum("0x" $10) * 0.75) - 48;
		#print COOLANT_TEMP_C > "/dev/stderr";
		FOUND=1;
		}
					
		#IAT
		if (CURRENT_DATA == "CD7AE610CE") {
		IAT_C=(strtonum("0x" $10) *0.75) - 48;
		#print "IAT:" IAT_C > "/dev/stderr";
		FOUND=1;
		}
					
		#AAT
		if (CURRENT_DATA == "CD7AE61009") {
		AAT_C=(strtonum("0x" $10) *0.75) - 48;
		#print "AAT:" AAT_C > "/dev/stderr";
		FOUND=1;
		}
					
		#Battery Voltage
		if (CURRENT_DATA == "CD7AE6100A") {
		BATTERY_V=strtonum("0x" $10) * 0.07;
		#print BATTERY_V > "/dev/stderr";
		FOUND=1;
		}
		
		#MPH
		if ($3 == "00300036") {
		VEH_SPEED=strtonum("0x" $11$12)/100*0.621;
		#print VEH_SPEED > "/dev/stderr";
		FOUND=1;
		}
						
		#Brake pedal
		if (CURRENT_DATA == "CE7AE6100C") {
		BRAKE=and(strtonum("0x" $10$11),strtonum("0x03FF"))*5/1024;
		#print BRAKE > "/dev/stderr";
		FOUND=1;
		}
					
		#SNIFFED FROM 0040001E
		if ($3 == "0040001E") {		
		#ENGINE SPEED
		ENG_SPEED=(strtonum("0x" $11$12) > 57344) ? (strtonum("0x" $11$12) - 57344) : 0;	#57344 is "E000" in decimal
		#print ENG_SPEED > "/dev/stderr";
						
		#ACCELERATOR PEDAL
		APP_min = 23	#measured 23 hex at 0% actual
		APP_max = 227	#measured 227 hex at 100% actual
		APP=((strtonum("0x" $8) - APP_min)/(APP_max-APP_min))*100;
		#print APP > "/dev/stderr";
		FOUND=1;
		}
		
		#write to output file dynamically
		if (FOUND) {
			#DEBUG LINE
			#print "[AWK] valid frame parsed (" $3 "). Updating file." > "/dev/stderr";
			#%-23 is String, 23char, left-aligned (Timestamp)
			#%-6.2f is Float, 6char, 2 decimal (COOLANT_TEMP_C)
			#%-5.2f is Float, 5char, 2 decimal (IAT)					
			#%-5.2f is Float, 5char, 2 decimal (AAT)					
			#%-5.2f is Float, 5char, 2 decimal (Battery)					
			#%-6.2f is Float, 6char, 2decimal (Veh_speed)
			#%-5.2f is Float, 5char, 2 decimal (Brake V)
			#%-4d is Integer, 4char (Eng_speed)
			#%-5.2f is Fload, 5char, 2 decimal (APP)
			printf "%-23s %-6.2f %-5.2f %-5.2f %-5.2f %-6.2f %-5.2f %-4d %-5.2f\n", $1, COOLANT_TEMP_C, IAT_C, AAT_C, BATTERY_V, VEH_SPEED, BRAKE, ENG_SPEED, APP > COUT;
			fflush(COUT);
			ROW_COUNT++;
		}
	}
}
'
