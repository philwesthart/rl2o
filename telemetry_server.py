from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import math

app = FastAPI()

# Initial data dictionary
telemetry={
    "rpm": 1,
    "speed": 1,
    "brake": 1,
    "acceleration": 1,
    "gg" : 1,
    "coolant_temp": 1,
    "iat": 1,
    "aat": 1,
    "battery_volt":1,
    "oil_temp":1,
    "oil_press":1,
    "afr":1,
    "trans_temp":1
}
t=0

def init():
    # put initialization code here
    pass

def get_gnss_data():
    # Call your gnss library
    gnss_data = {
        "lat" : 0,
        "long" : 0
    }

    # TODO replace with library call
    gnss_data["lat"] = 33.23
    gnss_data["long"] = 42.432

    return gnss_data

def get_can_bus_data():
    # See python can 
    # https://python-can.readthedocs.io/en/stable/_modules/can/util.html

    can_bus_data = {}

    return can_bus_data

@app.get("/telemetry")
def get_data():
    global telemetry
    global t
    t = t+1

    # TODO replace with CAN queries
    telemetry["rpm"] = int(5000 + 2000*math.sin(t/10.0))
    telemetry["mph"] = int(50 + 20*math.sin(t/10.0))

    gnss_data = get_gnss_data()
    telemetry["lat"] = gnss_data["lat"]

    can_bus_data = get_can_bus_data()
    telemetry["TBD"] = can_bus_data.lat

    return telemetry

app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Call the init function
init()
