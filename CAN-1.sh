#!/bin/bash
#NOTE: whenever this file is revised (or renamed), make sure to edit bootscript.service via sudo nano /etc/systemd/system/bootscript.service
#This script stops all sub-scripts, then restarts itself if the day has changed. 

#ctrl+c trigger
cleanup() {
	echo "Ctrl+C, running killsw-1..."
	/home/rlto/Desktop/Logs/Scripts/killsw-1.sh
	exit 0
}
trap cleanup SIGINT

cd "$(dirname "$0")" || exit 1
START_DATE=$(date +%F)
	
#create a folder with today's date yyyy-mm-dd
curr_date=$(date +%F)
mkdir -p "../$curr_date"
chown rlto:rlto /home/rlto/Desktop/Logs/$curr_date
#echo $PWD"/$curr_date"

#run transmit CANsend script
/home/rlto/Desktop/Logs/Scripts/cansend-1.sh &
#run sample-1.sh CAN sampling script (logs all CAN signals)
/home/rlto/Desktop/Logs/Scripts/sample-1.sh &
#run DAQ sampling script
sudo /home/rlto/Desktop/Logs/Scripts/DAQ/venv/bin/python3 /home/rlto/Desktop/Logs/Scripts/DAQ/DAQ-1.py &
#run processing script
/home/rlto/Desktop/Logs/Scripts/process-1.sh

#check if it's a new day
while [ "$(date +%F)" == "$START_DATE" ]; do
	sleep 3600
done

#killswitch if new day, then restart
/home/rlto/Desktop/Logs/Scripts/killsw-1.sh
exec "$0"
