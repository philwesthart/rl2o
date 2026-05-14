#!/bin/bash
#this script solely serves to STOP the sampling script service 

#stop systemd service
echo "Stopping BootScript.service systemd..."
sudo systemctl stop bootscript.service

#kill separate running scripts
echo "Ensuring script instances are terminated..."
#sudo pkill -f CAN-1.sh
sudo pkill -f sample-1.sh
sudo pkill -f cansend-1.sh
sudo pkill -f process-1.sh
sudo pkill -f DAQ-1.py

#fix final permissions
echo "Unlocking log files for rlto user"
sudo chown -R rlto:rlto /home/rlto/Desktop/Logs
sudo chmod -R 775 /home/rlto/Desktop/Logs

echo "Done"
