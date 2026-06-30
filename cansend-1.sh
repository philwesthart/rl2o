#!/bin/bash
#test script sending requests for data at a specified interval

trap 'kill 0' INT TERM
#long interval
send_request1() {
	while true; do
		cansend can0 000FFFFE#CD7AA610D8010000 #coolant temp
		sleep 0.05 #breather for data request
		cansend can0 000FFFFE#CD7AA610CE010000 #IAT
		sleep 0.05 #breather for data request
		cansend can0 000FFFFE#CD7AA61009010000 #AAT
		sleep 0.05 #breather for data request
		cansend can0 000FFFFE#CD7AA6100A010000 #battery voltage
		sleep 10
	done
}

#(future) 100ms interval
#send_request2() {
#	while true; do
		#cansend can0 000FFFFE#CD7AA61140010000 #vehicle speed
		#sleep 0.5
#	done
#}

#(future) 50ms interval
send_request3() {
	while true; do
		#cansend can0 000FFFFE#CD7AA6129D010000 #boost pressure
		#sleep 0.05 #breather for data request
		#cansend can0 000FFFFE#CD7AA61034010000 #AFR
		#sleep 0.05 #breather for data request
		cansend can0 000FFFFE#CD7AA6100C010000 #brake position
		sleep 0.1
	done
}

send_request1 &
#send_request2 &
send_request3 &
