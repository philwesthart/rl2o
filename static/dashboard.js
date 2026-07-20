const rpmGauge = new RadialGauge({
    renderTo: 'rpmGauge',
    width: 150,
    height: 150,
    units: "RPM",
    minValue: 0,
    maxValue: 10000,
    majorTicks: [
        "0","2000","4000","6000",
        "8000","10000"
    ],
    minorTicks: 4,
    strokeTicks: true,
    value: 0,
    highlights: [
        {
            from:0,
            to:8000,
            color:"rgba(0,255,0,.2)"
        },
        {
            from:8000,
            to:10000,
            color:"rgba(255,0,0,.4)"
        }
    ],
    colorPlate:"#00000000",
    colorNeedle:"#ff3333",
    colorNumbers:"#ffffff",
    colorUnits:"#ffffff",
    colorTitle:"#ffffff",
    animationDuration:15,
    animationRule:"linear"
}).draw();

const mphGauge = new RadialGauge({
    renderTo: 'mphGauge',
    width: 150,
    height: 150,
    units: "MPH",
    minValue: 0,
    maxValue: 160,
    majorTicks: [
        "0","20","40","60",
        "80","100","120",
        "140","160"
    ],
    minorTicks: 4,
    strokeTicks: true,
    value: 0,
    highlights: [
        {
            from:0,
            to:60,
            color:"rgba(0,255,0,.2)"
        },
        {
            from:60,
            to:100,
            color:"rgba(255,255,0,.3)"
        },
        {
            from:100,
            to:160,
            color:"rgba(255,0,0,.4)"
        }
    ],
    colorPlate:"#00000000",
    colorNeedle:"#ff3333",
    colorNumbers:"#ffffff",
    colorUnits:"#ffffff",
    colorTitle:"#ffffff",
    animationDuration:150,
    animationRule:"linear"
}).draw();

const brakeGauge = new LinearGauge({
    renderTo: "brakeGauge",
    width: 50,
    height: 150,
    minValue: 0,
    maxValue: 1,
    value: 0,
    units: "BRK",
    orientation: "vertical",
    // Fill direction
    barBeginCircle: false,
    // Hide unnecessary markings
    majorTicks: [],
    minorTicks: 0,
    strokeTicks: false,
    highlights: [],
    // Background
    colorPlate: "rgba(0,0,0,0)",
    // Red fill
    colorBar: "#ff0000",
    colorBarProgress: "#ff0000",

    // Remove text inside gauge
    valueBox: false,
    // Needle is not used
    colorNeedle: "transparent",
    animationDuration: 150,
    animationRule: "linear"
}).draw();

const accGauge = new LinearGauge({
    renderTo: "accGauge",
    width: 50,
    height: 150,
    minValue: 0,
    maxValue: 1,
    value: 0,
    units: "THR",
    orientation: "vertical",
    // Fill direction
    barBeginCircle: false,
    // Hide unnecessary markings
    majorTicks: [],
    minorTicks: 0,
    strokeTicks: false,
    highlights: [],
    // Background
    colorPlate: "rgba(0,0,0,0)",
    // Red fill
    colorBar: "#00ff00",
    colorBarProgress: "#00ff00",

    // Remove text inside gauge
    valueBox: false,
    // Needle is not used
    colorNeedle: "transparent",
    animationDuration: 150,
    animationRule: "linear"
}).draw();

function safeFixed(val, decimals = 0) {
    // formats numbers if null/undefined
    return (val !== undefined && val !== null && !isNaN(val)) ? Number(val).toFixed(decimals) : "0";
}

const elements = {
    coolantTemp: document.getElementById("coolantTemp"),
    iat: document.getElementById("iat"),
    aat: document.getElementById("aat"),
    batteryVoltage: document.getElementById("batteryVoltage"),
    oilTemp: document.getElementById("oilTemp"),
    oilPressure: document.getElementById("oilPressure"),
    afr: document.getElementById("afr"),
    transTemp: document.getElementById("transTemp")
};

setInterval(async () => {
    try {
        const res = await fetch("http://127.0.0.1:8000/telemetry");
        //const res = await fetch("/telemetry");
        if (!res.ok) return;
        const t = await res.json();
        if(!t) return;
        
        if (t.RPM !== undefined) rpmGauge.value = t.RPM;
        if (t.MPH !== undefined) mphGauge.value = t.MPH;
        if (t.brake !== undefined) brakeGauge.value = t.brake;
        if (t.throttle !== undefined) accGauge.value = t.throttle;
        if (elements.coolantTemp) elements.coolantTemp.textContent = `${safeFixed(t.coolant_temp, 0)} °C`;
        if (elements.iat) elements.iat.textContent = `${safeFixed(t.IAT, 0)} °C`;
        if (elements.aat) elements.aat.textContent = `${safeFixed(t.AAT, 0)} °C`;
        if (elements.batteryVoltage) elements.batteryVoltage.textContent = `${safeFixed(t.Battery_V, 1)} V`;
        if (elements.oilTemp) elements.oilTemp.textContent = `${safeFixed(t.oil_temp, 0)} °C`;
        if (elements.oilPressure) elements.oilPressure.textContent = `${safeFixed(t.oil_press, 0)} PSI`;
        if (elements.afr) elements.afr.textContent = `${safeFixed(t.AFR, 1)}`;
        if (elements.transTemp) elements.transTemp.textContent = `${safeFixed(t.trans_temp, 0)} °C`;
    } catch (err) {
        console.warn("[Dashboard] Fetch failed:", err);
    }
}, 100);
