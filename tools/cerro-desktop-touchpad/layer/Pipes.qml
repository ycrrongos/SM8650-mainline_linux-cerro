import QtQuick

Canvas {
    id: pipes
    property var trails: [[[3, 4]], [[19, 10]]]
    property var directions: [0, 2]
    readonly property var steps: [[1, 0], [0, 1], [-1, 0], [0, -1]]
    readonly property var colors: ["#738fc1", "#a078b1"]
    canvasSize: Qt.size(320, 144)

    Timer {
        interval: 115
        running: pipes.visible
        repeat: true
        onTriggered: {
            for (let i = 0; i < 2; i++) {
                const trail = pipes.trails[i];
                const last = trail[trail.length - 1];
                const direction = pipes.directions[i];
                const turn = Math.random();
                const first = (direction + (turn < 0.23 ? 1 : turn < 0.46 ? 3 : 0)) % 4;
                for (const step of [first, direction, (direction + 1) % 4, (direction + 3) % 4, (direction + 2) % 4]) {
                    const x = last[0] + pipes.steps[step][0];
                    const y = last[1] + pipes.steps[step][1];
                    if (x < 0 || x > 23 || y < 0 || y > 12)
                        continue;
                    trail.push([x, y]);
                    pipes.directions[i] = step;
                    break;
                }
                if (trail.length > 66)
                    trail.shift();
            }
            pipes.requestPaint();
        }
    }

    onPaint: {
        const ctx = getContext("2d");
        ctx.clearRect(0, 0, canvasSize.width, canvasSize.height);
        ctx.lineJoin = "round";
        for (let i = 0; i < trails.length; i++) {
            const points = trails[i];
            ctx.beginPath();
            for (let p = 0; p < points.length; p++) {
                const x = 7 + points[p][0] * 13;
                const y = 6 + points[p][1] * 11;
                if (p === 0)
                    ctx.moveTo(x, y);
                else
                    ctx.lineTo(x, y);
            }
            ctx.lineWidth = 5;
            ctx.strokeStyle = colors[i];
            ctx.stroke();
            ctx.lineWidth = 2;
            ctx.strokeStyle = "#23243c";
            ctx.stroke();
        }
    }
}
