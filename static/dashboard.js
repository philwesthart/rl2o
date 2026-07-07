setInterval(async () => {
    const t =
        await fetch("/telemetry")
        .then(r => r.json());

    speed.innerText =
        `${t.speed} mph`;

    rpm.innerText =
        `${t.rpm} rpm`;
}, 100);