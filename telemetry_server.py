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

@app.get("/telemetry")
def get_data():
    global telemetry
    global t
    t = t+1

    # TODO replace with CAN queries
    telemetry["rpm"] = int(5000 + 2000*math.sin(t/10.0))
    telemetry["mph"] = int(50 + 20*math.sin(t/10.0))

    return telemetry

app.mount("/", StaticFiles(directory="static", html=True), name="static")
