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
    readonly property color base: "#11111b"
    readonly property color surface: "#1e1e2e"
    readonly property color textColor: "#cdd6f4"
    readonly property color muted: "#a6adc8"
    readonly property color accent: "#cba6f7"
    readonly property color secondary: "#89b4fa"

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.now = new Date();
            sample.running = true;
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
                if (values.length === 32 && values.every(Number.isFinite))
                    root.bands = values;
            }
        }
    }

    Variants {
        model: Quickshell.screens.filter(screen => screen.name === "DSI-1")
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            WlrLayershell.namespace: "cerro-touchpad-dashboard"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            exclusionMode: ExclusionMode.Ignore
            color: root.base
            mask: Region {}

            RowLayout {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                Rectangle {
                    Layout.preferredWidth: 310
                    Layout.fillHeight: true
                    radius: 26
                    color: root.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 9
                        Text {
                            text: "◉   CERRO  /  触摸板"
                            color: root.accent
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                        }
                        Item { Layout.fillHeight: true }
                        Text {
                            text: Qt.formatTime(root.now, "hh:mm")
                            color: root.textColor
                            font.pixelSize: 70
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: Qt.formatDate(root.now, "MMM d  ·  dddd")
                            color: root.muted
                            font.pixelSize: 18
                        }
                        Item { Layout.fillHeight: true }
                        Repeater {
                            model: [
                                ["电量", (root.stats.battery ?? "—") + "%"],
                                ["内存", (root.stats.ram ?? "—") + " / " + (root.stats.total ?? "—") + " GiB"],
                                ["SM8650 负载", root.stats.load ?? "—"]
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 34
                                radius: 17
                                color: "#313244"
                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 13
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData[0]
                                    color: root.muted
                                    font.pixelSize: 14
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 13
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData[1]
                                    color: root.textColor
                                    font.pixelSize: 14
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 26
                    color: root.surface
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 10
                        Text {
                            text: "♫   正在播放"
                            color: root.secondary
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.stats.title || "未播放音乐"
                            elide: Text.ElideRight
                            color: root.textColor
                            font.pixelSize: 30
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.stats.artist ?? ""
                            elide: Text.ElideRight
                            color: root.muted
                            font.pixelSize: 17
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 48
                            color: "#181825"
                            radius: 18
                            Row {
                                id: spectrum
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 4
                                Repeater {
                                    model: 32
                                    delegate: Item {
                                        required property int index
                                        width: Math.max(1, (spectrum.width - 31 * spectrum.spacing) / 32)
                                        height: spectrum.height
                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            width: parent.width
                                            height: Math.max(3, parent.height * (root.bands[index] ?? 0) / 1000)
                                            radius: width / 2
                                            color: index < 16 ? root.accent : root.secondary
                                        }
                                    }
                                }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.stats.lyric || "暂无同步歌词"
                            elide: Text.ElideRight
                            color: root.accent
                            font.pixelSize: 20
                        }
                    }
                }
            }
        }
    }
}
