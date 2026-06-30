#!/bin/bash
#this script samples all CAN data for SAMPLERATE, appends it to a file,
#then pauses for a random amount of time +-10% of SAMPLERATE.

#Definitions
SAMPLERATE=0.1  #Log/pause rate in seconds
ROW_LIMIT=300000	#300k originally
MAX_STORAGE=20 #GB
MAX_STORAGE=$((MAX_STORAGE*1000*1000)) #KB

#create directory if doesn't exist
mkdir -p "/home/rlto/Desktop/Logs/$(date +%F)"

#initialize first file name
CURRENT_TIME=$(date +%H-%M-%S)
LOG_FILE="/home/rlto/Desktop/Logs/$(date +%F)/($CURRENT_TIME) CAN-all.log"

#write initial header
echo " Timestamp            CAN   ID         Lgh  Data" > "$LOG_FILE"
echo " -----------------------------------------------" >> "$LOG_FILE"

#####FUNCTION TO RECURSIVELY CLEAN UP FOLDER SIZE
cleanup_old() {
	#calculate current size KB
	CURRENT_SIZE=$(du -s "/home/rlto/Desktop/Logs" | cut -f1)
	#echo $CURRENT_SIZE
	while [ "$CURRENT_SIZE" -gt "$MAX_STORAGE" ]; do
		#Recursively find oldest file and delete it (-type f)
		OLDEST_FILE=$(find "/home/rlto/Desktop/Logs" -type f -name "*.log" -printf '%T+ %p\n' | sort | head -n 1 | cut -d' ' -f2-)
		
		if [ -n "$OLDEST_FILE" ]; then
			rm "$OLDEST_FILE"
			#recalculate if threshold still exceeded
			CURRENT_SIZE=$(du -s "/home/rlto/Desktop/Logs" | cut -f1)
		else
			break
		fi
	done
	#Delete empty subfolders left behind
	find "/home/rlto/Desktop/Logs" -type d -empty -delete
}
while true; do
    # -ta: Adds an epoch absolute timestamp
    timeout $SAMPLERATE candump -ta can0 >> "$LOG_FILE" 2>/dev/null
    
    #check rows if greater than ROW_LIMIT
    ROW_COUNT=$(wc -l < "$LOG_FILE")
    if [ "$ROW_COUNT" -ge $ROW_LIMIT ]; then
    	chown rlto:rlto "$LOG_FILE"
    	chmod 664 "$LOG_FILE"
    	sync
    	
    	#before creating new file, check if old files need deletion
    	cleanup_old
    	
    	CURRENT_TIME=$(date +%H-%M-%S)
    	LOG_FILE="/home/rlto/Desktop/Logs/$(date +%F)/($CURRENT_TIME) CAN-all.log"
    	echo " Timestamp            CAN   ID         Lgh  Data" > "$LOG_FILE"
    	echo " -----------------------------------------------" >> "$LOG_FILE"
    fi	
    
    # 2. Pause for a jitter duration
    JITTER=$(awk -v s="$SAMPLERATE" 'BEGIN{
    	srand ();
    	if (s < 0.1) {
    		print 0.1;
    	} else {
    		min = s * 0.9;
    		max = s * 1.1;
    		print min + rand() * (max - min)
    	}
    }')
    sleep $JITTER
done
