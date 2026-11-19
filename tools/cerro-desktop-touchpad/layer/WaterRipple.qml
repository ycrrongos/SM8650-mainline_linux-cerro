pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: water
    required property Item wallpaper
    readonly property vector2d delta: Qt.vector2d(1 / 144, 1 / 64)
    property vector2d pendingDrop: Qt.vector2d(0.5, 0.5)
    property bool pending: false
    property real strength: 0
    property bool diagnostic: false
    readonly property bool rendering: simulation.active

    function splash(x, y) {
        pendingDrop = Qt.vector2d(x, y);
        pending = true;
        simulation.active = true;
        stopTimer.restart();
    }

    Timer {
        id: stopTimer
        interval: 1250
        onTriggered: {
            simulation.active = false;
            water.pending = false;
            if (water.diagnostic)
                console.info("Cerro water idle");
        }
    }

    // A small half-float feedback texture preserves signed height and velocity.
    Loader {
        id: simulation
        anchors.fill: parent
        active: false
        sourceComponent: Item {
            id: field
            property vector2d center: Qt.vector2d(0.5, 0.5)
            Timer {
                interval: 33
                repeat: true
                running: true
                triggeredOnStart: true
                onTriggered: {
                    field.center = water.pendingDrop;
                    water.strength = water.pending ? 0.042 : 0;
                    water.pending = false;
                    simulationTexture.scheduleUpdate();
                }
            }
            ShaderEffect {
                id: step
                width: 144
                height: 64
                property var stateTexture: simulationTexture
                property vector2d dropCenter: field.center
                property real dropStrength: water.strength
                property vector2d delta: water.delta
                fragmentShader: Qt.resolvedUrl("shaders/update.frag.qsb")
            }
            ShaderEffectSource {
                id: simulationTexture
                sourceItem: step
                textureSize: Qt.size(144, 64)
                format: ShaderEffectSource.RGBA16F
                recursive: true
                live: false
                hideSource: true
                smooth: false
            }
            ShaderEffectSource {
                id: backgroundTexture
                sourceItem: water.wallpaper
                textureSize: Qt.size(800, 360)
                live: false
                hideSource: false
            }
            ShaderEffect {
                anchors.fill: parent
                property var wallpaper: backgroundTexture
                property var water: simulationTexture
                property vector2d delta:  Qt.vector2d(1 / 144, 1 / 64)
                fragmentShader: Qt.resolvedUrl("shaders/refract.frag.qsb")
            }
        }
    }
}
