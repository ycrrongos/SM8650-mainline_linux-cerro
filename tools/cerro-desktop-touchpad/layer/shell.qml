pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    property var stats: ({})
    property var bands: []
    property date now: new Date()
    property bool sound: false
    property string wallpaperUrl: ""
    property bool keyboardMode: false
    property bool switchVisible: false
    property real keyboardTop: 0
    property real switchLeft: 1
    property real switchBottom: 0
    property var keyboardKeys: []
    property var keyboardModifiers: []
    property int highlightedKey: -1
    signal touchRipple(real x, real y)
    property double lastSound: 0
    readonly property int dwell: Math.max(2000, Number(Quickshell.env("CERRO_CAROUSEL_MS")) || 12000)
    readonly property color ink: "#c4c9e8"
    readonly property color mint: "#a0d9c4"
    readonly property color violet: "#9c72c6"
    readonly property color blue: "#8fc6ef"
    onSoundChanged: {
        if (Quickshell.env("CERRO_CAROUSEL_MS") !== "")
            console.info("Cerro spectrum visible", sound);
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.now = new Date();
            sample.running = true;
            if (Date.now() - root.lastSound > 950)
                root.sound = false;
        }
    }
    Process {
        id: sample
        command: ["python3", Quickshell.shellPath("../telemetry.py")]
        stdout: SplitParser {
            onRead: line => { try { root.stats = JSON.parse(line); } catch (_) {} }
        }
    }
    Process {
        running: true
        command: ["cava", "-p", Quickshell.shellPath("../cava.conf")]
        stdout: SplitParser {
            onRead: line => {
                const values = line.trim().split(";").filter(v => v !== "").map(Number);
                if (values.length !== 32 || !values.every(Number.isFinite))
                    return;
                root.bands = values;
                if (values.some(value => value >= 4))
                    root.lastSound = Date.now();
                root.sound = Date.now() - root.lastSound < 850;
            }
        }
    }

    Process {
        running: true
        command: ["python3", Quickshell.shellPath("../wallpaper.py")]
        stdout: SplitParser {
            onRead: line => { if (line.trim()) root.wallpaperUrl = line.trim(); }
        }
    }
    Process {
        running: Quickshell.env("CERRO_TOUCHPAD_TRAY") === "1"
        command: ["python3", Quickshell.shellPath("../tray.py")]
    }

    Process {
        running: true
        command: ["python3", Quickshell.shellPath("../ripple-stream.py")]
        stdout: SplitParser {
            onRead: line => {
                if (line.startsWith("{")) {
                    try {
                        const state = JSON.parse(line);
                        if (state.keys !== undefined)
                            root.keyboardKeys = state.keys;
                        root.keyboardMode = state.keyboard;
                        root.switchVisible = state.switch;
                        root.keyboardTop = state.keyboardTop;
                        root.switchLeft = state.switchLeft;
                        root.switchBottom = state.switchBottom;
                        root.keyboardModifiers = state.modifiers;
                        if (state.key !== null && state.pressed) {
                            root.highlightedKey = state.key;
                            keyFlash.restart();
                        }
                    } catch (_) {}
                    return;
                }
                const point = line.trim().split(" ").map(Number);
                if (point.length === 2 && point.every(Number.isFinite)) {
                    root.touchRipple(point[0], point[1]);
                    if (Quickshell.env("CERRO_RIPPLE_SOCKET") !== "")
                        console.info("Cerro ripple sample accepted");
                }
            }
        }
    }

    Timer {
        id: keyFlash
        interval: 150
        onTriggered: root.highlightedKey = -1
    }

    component PanelText: Text {
        color: root.ink
        font.family: "Noto Sans Mono"
        font.pixelSize: 21
        elide: Text.ElideRight
    }

    component Digit: Item {
        id: digit
        required property string value
        width: value === ":" ? height * 0.22 : height * 0.60
        readonly property var patterns: ["abcdef", "bc", "abdeg", "abcdg",
            "bcfg", "acdfg", "acdefg", "abc", "abcdefg", "abcdfg"]
        Repeater {
            model: digit.value === ":" ? [] : ["a", "b", "c", "d", "e", "f", "g"]
            delegate: Rectangle {
                required property string modelData
                readonly property bool horizontal: "adg".includes(modelData)
                readonly property bool rightSegment: "bc".includes(modelData)
                readonly property bool lower: "ce".includes(modelData)
                readonly property real bar: digit.height * 0.105
                width: horizontal ? digit.width - bar * 1.8 : bar
                height: horizontal ? bar : digit.height / 2 - bar * 1.1
                x: horizontal ? bar * 0.9 : rightSegment ? digit.width - bar : 0
                y: horizontal ? (modelData === "a" ? 0 : modelData === "g"
                    ? (digit.height - bar) / 2 : digit.height - bar)
                    : lower ? digit.height / 2 + bar * 0.4 : bar * 0.85
                radius: 1.5
                color: digit.patterns[Number(digit.value)]?.includes(modelData)
                    ? root.mint : "#263846"
            }
        }
        Repeater {
            model: digit.value === ":" ? 2 : 0
            delegate: Rectangle {
                required property int index
                width: digit.width * 0.55
                height: width
                radius: 2
                anchors.horizontalCenter: digit.horizontalCenter
                y: digit.height * (index === 0 ? 0.3 : 0.61)
                color: root.mint
            }
        }
    }

    Variants {
        model: Quickshell.screens.filter(screen => screen.name === "DSI-1")
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            WlrLayershell.namespace: "cerro-touchpad-dashboard"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            exclusionMode: ExclusionMode.Ignore
            color: "#080813"
            mask: Region {}

            Image {
                id: wallpaperImage
                anchors.fill: parent
                source: root.wallpaperUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
            WaterRipple {
                id: waterRipple
                anchors.fill: parent
                wallpaper: wallpaperImage
                diagnostic: Quickshell.env("CERRO_RIPPLE_SOCKET") !== ""
            }
            Connections {
                target: root
                function onTouchRipple(x, y) { waterRipple.splash(x, y); }
            }

            KeyboardGrid {
                visible: root.keyboardMode
                y: parent.height * root.keyboardTop
                width: parent.width
                height: parent.height - y
                keys: root.keyboardKeys
                modifiers: root.keyboardModifiers
                highlightedKey: root.highlightedKey
            }

            Rectangle {
                z: 1
                visible: root.switchVisible
                x: parent.width * root.switchLeft + 4
                y: 4
                width: parent.width - x - 4
                height: parent.height * root.switchBottom - 8
                radius: Math.min(10, height / 3)
                color: "#80171727"

                Text {
                    anchors.centerIn: parent
                    text: root.keyboardMode ? "触摸板" : "键盘"
                    color: root.ink
                    font.pixelSize: Math.max(1, Math.min(parent.height * 0.48, parent.width / 4))
                }
            }

            Item {
                id: composition
                anchors.fill: parent
                visible: !root.keyboardMode
                property int page: 0
                property int effect: -1
                property real shiftX: 0
                property real shiftY: 0
                property real dx: 0
                property real dy: 0
                property real zoom: 1
                property real tilt: 0
                readonly property bool diagnostic: Quickshell.env("CERRO_CAROUSEL_MS") !== ""

                function advance() {
                    if (transition.running)
                        return;
                    effect = (effect + 1 + Math.floor(Math.random() * 3)) % 4;
                    transition.start();
                }

                Timer {
                    interval: root.dwell
                    running: !root.keyboardMode
                    repeat: true
                    onTriggered: composition.advance()
                }
                SequentialAnimation {
                    id: transition
                    ParallelAnimation {
                        NumberAnimation { target: pageContent; property: "opacity"; to: 0; duration: 210; easing.type: Easing.InCubic }
                        NumberAnimation { target: composition; property: "dx"; to: composition.effect === 0 ? -48 : 0; duration: 210; easing.type: Easing.InCubic }
                        NumberAnimation { target: composition; property: "dy"; to: composition.effect === 1 ? 32 : 0; duration: 210; easing.type: Easing.InCubic }
                        NumberAnimation { target: composition; property: "zoom"; to: composition.effect === 2 ? 0.84 : 1; duration: 210; easing.type: Easing.InCubic }
                        NumberAnimation { target: composition; property: "tilt"; to: composition.effect === 3 ? -7 : 0; duration: 210; easing.type: Easing.InCubic }
                    }
                    ScriptAction {
                        script: {
                            composition.page = (composition.page + 1) % 4;
                            composition.shiftX = Math.random() * 52 - 26;
                            composition.shiftY = Math.random() * 36 - 18;
                            composition.dx *= -1;
                            composition.dy *= -1;
                            composition.tilt *= -1;
                            if (composition.diagnostic)
                                console.info("Cerro carousel", composition.page, composition.effect,
                                    "spectrum", root.sound, "shift", composition.shiftX, composition.shiftY);
                        }
                    }
                    ParallelAnimation {
                        NumberAnimation { target: pageContent; property: "opacity"; to: 1; duration: 440; easing.type: Easing.OutCubic }
                        NumberAnimation { target: composition; property: "dx"; to: 0; duration: 520; easing.type: Easing.OutQuint }
                        NumberAnimation { target: composition; property: "dy"; to: 0; duration: 520; easing.type: Easing.OutQuint }
                        NumberAnimation { target: composition; property: "zoom"; to: 1; duration: 520; easing.type: Easing.OutBack }
                        NumberAnimation { target: composition; property: "tilt"; to: 0; duration: 520; easing.type: Easing.OutQuint }
                    }
                }

                Item {
                    id: pageContent
                    visible: !root.keyboardMode
                    width: parent.width - 108
                    height: parent.height * (root.sound ? 0.58 : 0.84)
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: composition.shiftX + composition.dx
                    anchors.verticalCenterOffset: composition.shiftY + composition.dy - (root.sound ? parent.height * 0.12 : 0)
                    scale: composition.zoom
                    rotation: composition.tilt
                    Behavior on height { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }

                    Loader {
                        anchors.fill: parent
                        anchors.margins: 16
                        sourceComponent: [clockPage, hardwarePage, musicPage, pipesPage][composition.page]
                    }
                }

                Item {
                    id: spectrum
                    visible: root.sound && !root.keyboardMode
                    width: parent.width - 108
                    height: parent.height * 0.24
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.horizontalCenterOffset: -composition.shiftX
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 22 + composition.shiftY * 0.25

                    Row {
                        id: bars
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4
                        Repeater {
                            model: 32
                            delegate: Item {
                                required property int index
                                width: Math.max(1, (bars.width - 31 * bars.spacing) / 32)
                                height: bars.height
                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width
                                    height: parent.height * Math.min(1, (root.bands[parent.index] ?? 0) / 1000)
                                    radius: 2
                                    gradient: Gradient {
                                        GradientStop { position: 0; color: root.blue }
                                        GradientStop { position: 1; color: "#5434a3" }
                                    }
                                    Behavior on height { NumberAnimation { duration: 65; easing.type: Easing.OutCubic } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: pipesPage
        Pipes {}
    }
    Component {
        id: clockPage
        Item {
            id: clockContainer
            Column {
                anchors.centerIn: parent
                spacing: 16
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 9
                    Repeater {
                        model: Qt.formatTime(root.now, "hh:mm:ss").split("")
                        delegate: Digit {
                            required property string modelData
                            value: modelData
                            height: Math.min(clockContainer.width * 0.22, clockContainer.height * 0.65)
                        }
                    }
                }
                PanelText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Qt.formatDate(root.now, "yyyy-MM-dd")
                    font.pixelSize: 16
                }
            }
        }
    }
    Component {
        id: hardwarePage
        RowLayout {
            id: hw
            spacing: 9
            Repeater {
                model: [
                    ["▰", (root.stats.battery ?? "—") + "%", root.mint],
                    ["▥", (root.stats.ram ?? "—") + " / " + (root.stats.total ?? "—"), root.blue],
                    ["⌁", root.stats.load ?? "—", root.violet]
                ]
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    color: "transparent"
                    Column {
                        anchors.centerIn: parent
                        spacing: 10
                        PanelText {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData[0]
                            font.pixelSize: 38
                            color: modelData[2]
                        }
                        PanelText {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData[1]
                            font.pixelSize: 30
                        }
                    }
                }
            }
        }
    }
    Component {
        id: musicPage
        ColumnLayout {
            spacing: 8
            Item { Layout.fillHeight: true }
            PanelText {
                text: "♫"
                color: root.mint
                font.pixelSize: 48
                Layout.alignment: Qt.AlignHCenter
            }
            PanelText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.stats.title ?? ""
                font.pixelSize: 46
                horizontalAlignment: Text.AlignHCenter
            }
            PanelText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.stats.artist ?? ""
                font.pixelSize: 16
                horizontalAlignment: Text.AlignHCenter
            }
            PanelText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.stats.lyric ?? ""
                color: root.mint
                horizontalAlignment: Text.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }
    }
}
