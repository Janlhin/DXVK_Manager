import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The dialog that stores the current selection as a named preset.
Dialog {
    id: presetDialog

    signal presetConfirmed(string name)

    modal: true
    anchors.centerIn: parent
    width: 400
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
            text: qsTr("保存为预设")
            color: Th.text
            font.pixelSize: Th.fontTitle
            font.bold: true
        }
    }

    contentItem: Column {
        leftPadding: Th.space4
        rightPadding: Th.space4
        topPadding: Th.space1
        bottomPadding: Th.space2
        spacing: Th.space2

        Text {
            width: presetDialog.availableWidth - Th.space6
            text: qsTr("把当前勾选的所有选项保存为自定义预设，之后可在任意游戏上一键套用。")
            color: Th.textMuted
            font.pixelSize: Th.fontCaption
            wrapMode: Text.WordWrap
        }

        TextField {
            id: presetNameField
            width: presetDialog.availableWidth - Th.space6
            placeholderText: qsTr("预设名称，例如：赛博朋克专用")
            color: Th.text
            placeholderTextColor: Th.textDim
            font.pixelSize: Th.fontSmall
            background: Rectangle {
                radius: Th.radiusControl
                color: Th.surfaceAlt
                border.width: 1
                border.color: presetNameField.activeFocus ? Th.accent : Th.border
            }
            onAccepted: savePresetButton.clicked()
        }
    }

    footer: Item {
        height: 52

        Text {
            anchors.left: parent.left
            anchors.leftMargin: Th.space4
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("「性能优先」「兼容优先」「纯净」为内置预设，不可覆盖。")
            color: Th.textDim
            font.pixelSize: Th.fontCaption
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: Th.space4
            anchors.verticalCenter: parent.verticalCenter
            spacing: Th.space2

            Button {
                id: savePresetButton
                text: qsTr("保存")
                padding: 6
                onClicked: {
                    if (presetNameField.text.trim() !== "")
                        presetDialog.presetConfirmed(presetNameField.text)
                    presetDialog.close()
                }
                background: Rectangle {
                    radius: Th.radiusControl
                    color: parent.hovered ? Th.primaryHover : Th.primary
                }
                contentItem: Text {
                    text: parent.text
                    color: Th.primaryText
                    font.pixelSize: Th.fontCaption
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                text: qsTr("取消")
                padding: 6
                onClicked: presetDialog.close()
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

    function openWithName() {
        presetNameField.text = ""
        presetDialog.open()
    }
}
