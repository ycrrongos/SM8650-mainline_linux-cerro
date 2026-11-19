pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: pool
    property int next: 0

    function splash(x, y) {
        const ripple = rings.itemAt(next);
        if (!ripple)
            return;
        next = (next + 1) % rings.count;
        ripple.begin(x * width, y * height);
    }

    Repeater {
        id: rings
        model: 8
        delegate: Item {
            id: ripple
            property real progress: 1
            visible: progress < 1
            opacity: 0.55 * (1 - progress) * (1 - progress)
            width: 0
            height: 0

            function begin(px, py) {
                expand.stop();
                x = px;
                y = py;
                progress = 0;
                expand.start();
            }

            NumberAnimation {
                id: expand
                target: ripple
                property: "progress"
                to: 1
                duration: 420
                easing.type: Easing.OutQuad
            }
            Repeater {
                model: 2
                delegate: Rectangle {
                    required property int index
                    anchors.centerIn: ripple
                    width: 14 + ripple.progress * (index === 0 ? 130 : 87)
                    height: width
                    radius: width / 2
                    border.width: index === 0 ? 1.5 : 1
                    border.color: index === 0 ? "#b9e6ff" : "#a89cff"
                    color: "transparent"
                }
            }
        }
    }
}
