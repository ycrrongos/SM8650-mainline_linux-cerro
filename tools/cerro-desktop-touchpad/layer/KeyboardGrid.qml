import QtQuick

Rectangle {
    id: grid
    required property var keys
    required property var modifiers
    required property int highlightedKey
    color: "#dd171727"

    Repeater {
        model: grid.visible ? grid.keys : []
        delegate: Rectangle {
            id: key
            required property var modelData
            readonly property bool selected: grid.highlightedKey === modelData.code
                || grid.modifiers.includes(modelData.code)
            x: grid.width * modelData.x + 2
            y: grid.height * modelData.y + 2
            width: grid.width * modelData.w - 4
            height: grid.height * modelData.h - 4
            radius: Math.min(12, height * 0.16)
            color: selected ? "#526482" : "#28273c"

            Text {
                anchors.centerIn: parent
                text: key.modelData.label
                color: "#c4c9e8"
                font.pixelSize: Math.max(1, Math.min(key.width * 0.37, key.height * 0.37))
            }
        }
    }
}
