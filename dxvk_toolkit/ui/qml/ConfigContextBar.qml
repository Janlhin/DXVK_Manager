import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The second bar of the configuration page: what is being edited (the
// target picker and the disk status badge) on the left, the preset and
// bulk actions on the right.
Rectangle {
    id: contextBar

    property var targetList: []
    property int targetIndex: 0
    property var presetList: []
    property string statusLabel: ""
    property string statusKind: "muted"
    property string gameKey: ""
    property bool showStatus: false

    signal targetActivated(int index)
    signal presetActivated(string name)
    signal savePresetRequested()
    signal clearRequested()
    signal resetRequested()

    height: 46
    color: Th.surface

    Row {
        anchors.left: parent.left
        anchors.leftMargin: Th.pad
        anchors.verticalCenter: parent.verticalCenter
        spacing: Th.space2

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("作用对象")
            color: Th.textMuted
            font.pixelSize: Th.fontCaption
        }

        ComboBox {
            id: targetPicker
            width: 240
            model: contextBar.targetList
            textRole: "label"
            currentIndex: contextBar.targetIndex
            font.pixelSize: Th.fontSmall
            onActivated: contextBar.targetActivated(currentIndex)
            background: Rectangle {
                radius: Th.radiusControl
                color: Th.surfaceAlt
                border.width: 1
                border.color: targetPicker.activeFocus ? Th.accent : Th.border
            }
            contentItem: Text {
                leftPadding: Th.space2
                rightPadding: Th.space2
                text: targetPicker.displayText
                color: Th.text
                font.pixelSize: Th.fontSmall
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
            indicator: Text {
                x: targetPicker.width - width - Th.space2
                y: (targetPicker.height - height) / 2
                text: "▾"
                color: Th.textMuted
                font.pixelSize: Th.fontSmall
            }
            popup: Popup {
                y: targetPicker.height + 4
                width: targetPicker.width
                implicitHeight: Math.min(contentItem.implicitHeight + Th.space2, 340)
                padding: Th.space1
                background: Rectangle {
                    radius: Th.radiusControl
                    color: Th.surfaceAlt
                    border.width: 1
                    border.color: Th.borderStrong
                }
                contentItem: ListView {
                    implicitHeight: contentHeight
                    model: targetPicker.popup.visible ? targetPicker.delegateModel : null
                    clip: true
                    delegate: ItemDelegate {
                        width: targetPicker.width - Th.space2
                        contentItem: Text {
                            text: modelData.label
                            color: Th.text
                            font.pixelSize: Th.fontSmall
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: Th.radiusControl - 2
                            color: parent.hovered ? Th.surfaceHover : "transparent"
                        }
                    }
                }
            }
        }

        StatusChip {
            anchors.verticalCenter: parent.verticalCenter
            // 默认目标下徽章文案与左侧下拉框完全重复；仅游戏目标时
            // 显示磁盘同步状态（已写入 / 与磁盘文件不同 / 未写入）。
            visible: contextBar.showStatus
            text: contextBar.statusLabel
            kind: contextBar.statusKind
        }
    }

    // Bulk actions live on the right, visually separate from the
    // "what am I editing" group on the left.
    Row {
        anchors.right: parent.right
        anchors.rightMargin: Th.pad
        anchors.verticalCenter: parent.verticalCenter
        spacing: Th.space2

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("预设")
            color: Th.textMuted
            font.pixelSize: Th.fontCaption
        }

        ComboBox {
            id: presetPicker
            width: 150
            model: contextBar.presetList
            currentIndex: -1
            font.pixelSize: Th.fontSmall
            displayText: currentIndex < 0 ? qsTr("选择预设…") : currentText
            onActivated: {
                var name = contextBar.presetList[currentIndex]
                presetPicker.currentIndex = -1
                if (name !== undefined && name !== "")
                    contextBar.presetActivated(name)
            }
            background: Rectangle {
                radius: Th.radiusControl
                color: Th.surfaceAlt
                border.width: 1
                border.color: presetPicker.activeFocus ? Th.accent : Th.border
            }
            contentItem: Text {
                leftPadding: Th.space2
                rightPadding: Th.space2
                text: presetPicker.displayText
                color: presetPicker.currentIndex < 0 ? Th.textDim : Th.text
                font.pixelSize: Th.fontSmall
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
            indicator: Text {
                x: presetPicker.width - width - Th.space2
                y: (presetPicker.height - height) / 2
                text: "▾"
                color: Th.textMuted
                font.pixelSize: Th.fontSmall
            }
            popup: Popup {
                y: presetPicker.height + 4
                width: presetPicker.width + 40
                implicitHeight: Math.min(contentItem.implicitHeight + Th.space2, 280)
                padding: Th.space1
                background: Rectangle {
                    radius: Th.radiusControl
                    color: Th.surfaceAlt
                    border.width: 1
                    border.color: Th.borderStrong
                }
                contentItem: ListView {
                    implicitHeight: contentHeight
                    model: presetPicker.popup.visible ? presetPicker.delegateModel : null
                    clip: true
                    delegate: ItemDelegate {
                        width: presetPicker.width + 40 - Th.space2
                        contentItem: Text {
                            text: modelData
                            color: Th.text
                            font.pixelSize: Th.fontSmall
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: Th.radiusControl - 2
                            color: parent.hovered ? Th.surfaceHover : "transparent"
                        }
                    }
                }
            }
        }

        MiniButton {
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("存为预设")
            onClicked: contextBar.savePresetRequested()
        }

        MiniButton {
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("清空")
            onClicked: contextBar.clearRequested()
        }

        MiniButton {
            anchors.verticalCenter: parent.verticalCenter
            visible: contextBar.gameKey !== ""
            text: qsTr("重置为默认")
            onClicked: contextBar.resetRequested()
        }
    }
}
