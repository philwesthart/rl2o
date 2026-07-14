setInterval(async () => {
    const t =
        await fetch("/telemetry")
        .then(r => r.json());

    rpmGauge.value = t.rpm
    mphGauge.value = t.mph

        document.getElementById("coolantTemp").innerHTML =
        `${t.coolant_temp.toFixed(0)} °F`;

    document.getElementById("iat").innerHTML =
        `${t.iat.toFixed(0)} °F`;

    document.getElementById("aat").innerHTML =
        `${t.aat.toFixed(0)} °F`;

    document.getElementById("batteryVoltage").innerHTML =
        `${t.battery_volt.toFixed(1)} V`;

    document.getElementById("oilTemp").innerHTML =
        `${t.oil_temp.toFixed(0)} °F`;

    document.getElementById("oilPressure").innerHTML =
        `${t.oil_press.toFixed(0)} PSI`;

    document.getElementById("afr").innerHTML =
        `${t.afr.toFixed(1)}`;

    document.getElementById("transTemp").innerHTML =
        `${t.trans_temp.toFixed(0)} °F`;

}, 10);


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
    colorBar: "#00ff00",
    colorBarProgress: "#00ff00",

    // Remove text inside gauge
    valueBox: false,
    // Needle is not used
    colorNeedle: "transparent",
    animationDuration: 150,
    animationRule: "linear"
}).draw();
