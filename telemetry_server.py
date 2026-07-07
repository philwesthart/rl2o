from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import math

app = FastAPI()

# Initial data dictionary
telemetry={
    "rpm": 1,
    "speed": 0,
    "brake": 0,
    "acceleration": 0,
    "gg" : 0,
    "coolant_temp": 0,
    "iat": 0,
    "aat": 0,
    "battery_volt":0,
    "oil_temp":0,
    "oil_press":0,
    "afr":0,
    "trans_temp":0
}

t=0

@app.get("/telemetry")
def get_data():
    global telemetry
    global t
    t = t+1

    telemetry["rpm"] = int(5000 + 2000*math.sin(t/10.0))
    telemetry["mph"] = int(50 + 20*math.sin(t/10.0))

    return telemetry

app.mount("/", StaticFiles(directory="static", html=True), name="static")
