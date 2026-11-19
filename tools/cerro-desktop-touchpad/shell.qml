import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root
    property var stats: ({})
    property var bands: []
    property string clock: Qt.formatDateTime(new Date(), "hh:mm  ·  MM/dd")

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.clock = Qt.formatDateTime(new Date(), "hh:mm  ·  MM/dd");
            statsProcess.running = true;
        }
    }

    Process {
        id: statsProcess
        command: ["python3", Quickshell.shellPath("telemetry.py")]
        stdout: SplitParser {
            onRead: line => { try { root.stats = JSON.parse(line); } catch (_) {} }
        }
    }

    Process {
        running: true
        command: ["cava", "-p", Quickshell.shellPath("cava.conf")]
        stdout: SplitParser {
            onRead: line => {
                const bins = line.split(";").filter(x => x.length > 0).map(Number);
                if (bins.length === 32 && bins.every(x => Number.isFinite(x)))
                    root.bands = bins;
            }
        }
    }

    FloatingWindow {
        title: "Cerro Touchpad Dashboard Preview"
        implicitWidth: 960
        implicitHeight: 420
        color: "#11141c"

        Column {
            anchors.fill: parent
            anchors.margins: 36
            spacing: 14

            Text { text: root.clock; font.pixelSize: 52; color: "#e1e8fd" }
            Text {
                text: "SM8650    ·    LOAD " + (root.stats.load ?? "—")
                    + "    ·    RAM " + (root.stats.ram ?? "—") + "/" + (root.stats.total ?? "—")
                    + " GiB    ·    BAT " + (root.stats.battery ?? "—") + "%"
                color: "#a8b4ce"
                font.pixelSize: 18
            }
            Text {
                width: parent.width
                elide: Text.ElideRight
                text: root.stats.title || "未播放音乐"
                color: "#e1e8fd"
                font.pixelSize: 32
            }
            Text { text: root.stats.artist ?? ""; color: "#a8b4ce"; font.pixelSize: 18 }
            Row {
                height: 76
                spacing: 5
                Repeater {
                    model: 32
                    delegate: Item {
                        required property int index
                        width: 16
                        height: 76
                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: Math.max(3, Math.min(76, 76 * (root.bands[index] ?? 0) / 1000))
                            radius: 4
                            color: "#9fbaff"
                        }
                    }
                }
            }
            Text {
                width: parent.width
                elide: Text.ElideRight
                text: root.stats.lyric || "暂无同步歌词"
                color: "#c4d5ff"
                font.pixelSize: 24
            }
        }
    }
}
