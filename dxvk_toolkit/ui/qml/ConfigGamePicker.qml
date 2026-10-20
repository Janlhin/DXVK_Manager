import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The dialog that asks which game the generated dxvk.conf should be
// written into.
Dialog {
    id: gamePicker
    objectName: "gamePicker"

    signal gameChosen(string key)

    modal: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 120, 560)
    height: Math.min(parent.height - 120, 520)
    padding: 0

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        color: Th.surface
        radius: Th.radiusPanel
        border.width: 1
        border.color: Th.borderStrong
    }

    header: Item {
        height: 52

        Text {
            anchors.left: parent.left
            anchors.leftMargin: Th.space4
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("把 dxvk.conf 写入哪个游戏？")
            color: Th.text
            font.pixelSize: Th.fontTitle
            font.bold: true
        }
    }

    contentItem: ListView {
        id: pickerList
        clip: true
        model: gamePicker.visible ? bridge.gameOptions() : []
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        delegate: Rectangle {
            width: pickerList.width
            height: 54
            color: pickHover.containsMouse ? Th.surfaceHover : "transparent"

            MouseArea {
                id: pickHover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    gamePicker.gameChosen(modelData.key)
                    gamePicker.close()
                }
            }

            Column {
                anchors.left: parent.left
                anchors.leftMargin: Th.space4
                anchors.right: parent.parent.right
                anchors.rightMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1

                Text {
                    width: parent.width
                    text: modelData.label
                    color: Th.text
                    font.pixelSize: Th.fontBody
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: modelData.path
                    color: Th.textDim
                    font.pixelSize: Th.fontCaption
                    elide: Text.ElideMiddle
                }
            }
        }
    }

    footer: Item {
        height: 48

        Text {
            anchors.left: parent.left
            anchors.leftMargin: Th.space4
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("写入前会把已有的 dxvk.conf 备份为 .bkp")
            color: Th.textDim
            font.pixelSize: Th.fontCaption
        }

        Button {
            anchors.right: parent.right
            anchors.rightMargin: Th.space4
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("关闭")
            padding: 6
            onClicked: gamePicker.close()
            background: Rectangle {
                radius: Th.radiusControl
                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
            }
            contentItem: Text {
                text: parent.text
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
