setInterval(async () => {
    const t =
        await fetch("/telemetry")
        .then(r => r.json());

    speed.innerText =
        `${t.mph} mph`;

    rpm.innerText =
        `${t.rpm} rpm`;

    rpmGauge.value = t.rpm
    mphGauge.value = t.mph
}, 100);

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