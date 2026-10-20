import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The list of configuration options in the middle column.
//
// It owns its own documentation card and hover tip: both are bound to a
// single delegate row, and a delegate can be destroyed by the list while
// the card is open, so the card must live next to the list rather than
// in the page.
ListView {
    id: optionList
    objectName: "optionList"

    // The sections the user has folded away. The page keeps a mirror of
    // this for its header arrows; the list is where it is edited.
    property var collapsedSections: ({})

    // Emitted when a row's value changed, so the page can mark the
    // preview as stale.
    signal optionChanged()

    // Emitted when the import message must be cleared (the user typed a
    // new value by hand).
    signal importMessageCleared()

    clip: true
    model: configModel
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {
        policy: ScrollBar.AsNeeded
        width: 8
        background: Item {}
        contentItem: Rectangle {
            implicitWidth: 6
            radius: Th.radiusMicro
            color: Th.borderStrong
            opacity: parent.pressed ? 1.0 : 0.6
        }
    }

    add: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1
                          duration: 160; easing.type: Easing.OutCubic }
    }

    Text {
        anchors.centerIn: parent
        visible: configModel.optionCount === 0
        width: Math.min(420, optionList.width - 48)
        text: qsTr("还没有可用的配置选项。\n先到「版本库」下载任意一个 DXVK 版本（自带参考文件），或到「设置」手动指定一个 dxvk.conf。")
        color: Th.textDim
        font.pixelSize: Th.fontBody
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }

    WheelHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function (wheel) {
            var step = 48 * 3
            var delta = wheel.pixelDelta.y !== 0
                      ? wheel.pixelDelta.y * 2
                      : (wheel.angleDelta.y / 120) * step
            var limit = Math.max(0, optionList.contentHeight - optionList.height)
            optionList.contentY = Math.max(0, Math.min(limit, optionList.contentY - delta))
            wheel.accepted = true
        }
    }

    // --- custom tool tip ------------------------------------------------
    Timer {
        id: tipTimer
        property string body: ""
        property var row: null
        interval: 420
        repeat: false
        onTriggered: {
            optionTip.body = body
            optionTip.open()
            optionTip.reposition(row, 0)
        }
    }

    DarkTip {
        id: optionTip
        function reposition(row, offsetY) {
            if (!row)
                return
            var point = row.mapToItem(optionList, 0, offsetY + 24)
            x = Math.max(Th.space4, Math.min(point.x + 48, optionList.width - width - Th.space4))
            y = Math.max(Th.space4, Math.min(point.y, optionList.height - height - Th.space4))
        }
    }

    ConfigDocCard {
        id: docCard
    }

    delegate: Rectangle {
        id: optionRow
        required property int index
        required property string rowKind
        required property string optionKey
        required property string label
        required property string description
        required property string summary
        required property var doc
        required property string example
        required property bool optionEnabled
        required property bool isBoolean
        required property string value
        required property string build

        width: optionList.width
        height: optionRow.rowKind === "header" ? 32 : 48
        color: optionRow.rowKind === "header"
               ? Th.surface
               : (rowHover.containsMouse ? Th.surfaceHover
                                         : (index % 2 === 0 ? Th.bg : Th.surfaceRaised))

        Behavior on color { ColorAnimation { duration: 120 } }

        MouseArea {
            id: rowHover
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            onEntered: {
                if (optionRow.rowKind === "header" || optionRow.description === "")
                    return
                tipTimer.body = optionRow.description
                tipTimer.row = optionRow
                tipTimer.restart()
            }
            onExited: {
                tipTimer.stop()
                optionTip.close()
            }
            onPositionChanged: {
                if (optionTip.visible)
                    optionTip.reposition(optionRow, mouse.y)
            }
        }

        // Header rows fold/unfold their section (rowHover ignores buttons).
        MouseArea {
            anchors.fill: parent
            enabled: optionRow.rowKind === "header"
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                var map = optionList.collapsedSections
                if (map[optionRow.label])
                    delete map[optionRow.label]
                else
                    map[optionRow.label] = true
                optionList.collapsedSections = map
                bridge.toggleSection(optionRow.label)
            }
        }

        Text {
            id: headerArrow
            visible: optionRow.rowKind === "header"
            anchors.left: parent.left
            anchors.leftMargin: Th.space3
            anchors.bottom: headerLine.top
            anchors.bottomMargin: Th.space1
            text: optionList.collapsedSections[optionRow.label] ? "▸" : "▾"
            color: Th.textMuted
            font.pixelSize: Th.fontCaption
        }

        Text {
            visible: optionRow.rowKind === "header"
            anchors.left: headerArrow.right
            anchors.leftMargin: Th.space1
            anchors.bottom: headerLine.top
            anchors.bottomMargin: Th.space1
            text: optionRow.label
            color: Th.text
            font.pixelSize: Th.fontSubtitle
            font.bold: true
        }

        Rectangle {
            id: headerLine
            visible: optionRow.rowKind === "header"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: Th.space3
            anchors.rightMargin: Th.space3
            height: 2
            color: Th.accent
            opacity: 0.5
        }

        Column {
            visible: optionRow.rowKind !== "header"
            anchors.left: parent.left
            anchors.leftMargin: Th.space3
            anchors.right: optionControls.left
            anchors.rightMargin: Th.space3
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            Row {
                width: parent.width
                spacing: Th.space2

                Text {
                    text: optionRow.label
                    color: optionRow.optionEnabled ? Th.text : Th.textMuted
                    font.pixelSize: Th.fontSubtitle
                    font.bold: true
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, parent.width
                                    - (forkBadge.visible ? forkBadge.width + Th.space2 : 0))
                }

                // Only the GPLAsync fork provides this option; upstream
                // dxvk.conf does not contain it at all.
                Rectangle {
                    id: forkBadge
                    visible: optionRow.build === "gplasync"
                    anchors.verticalCenter: parent.verticalCenter
                    radius: Th.radiusMicro
                    color: Th.statusBg("warn")
                    border.width: 1
                    border.color: Th.warn
                    implicitWidth: forkLabel.implicitWidth + Th.space2
                    implicitHeight: forkLabel.implicitHeight + Th.space1

                    Text {
                        id: forkLabel
                        x: (parent.width - width) / 2
                        y: (parent.height - height) / 2
                        text: qsTr("GPLAsync 专有")
                        color: Th.warn
                        font.pixelSize: Th.fontMicro
                    }
                }

                // §34 / T21: the full documentation card behind one click.
                // Hovering still shows the quick summary; the badge opens
                // the sectioned, scrollable card with the raw upstream
                // block - which never fit inside a hover tip.
                Text {
                    id: docBadge
                    visible: optionRow.rowKind !== "header" && optionRow.doc
                             && (optionRow.doc.summary !== undefined)
                    anchors.verticalCenter: parent.verticalCenter
                    leftPadding: 4
                    rightPadding: 4
                    text: "ⓘ"
                    color: docBadgeHover.containsMouse ? Th.accent : Th.textMuted
                    font.pixelSize: Th.fontSmall
                    font.bold: true

                    MouseArea {
                        id: docBadgeHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: docCard.openFor(optionRow)
                    }
                }
            }

            Text {
                width: parent.width
                visible: text !== ""
                text: optionRow.summary
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
                elide: Text.ElideRight
            }
        }

        // 每行右缘统一是开关（启用状态一眼可见，不再是最左侧的 16px
        // 复选框）；非布尔选项在开关左侧放值输入框。开关沿用原复选框
        // 语义（传当前输入框的值），行为不变。
        Row {
            id: optionControls
            anchors.right: parent.right
            anchors.rightMargin: Th.space3
            anchors.verticalCenter: parent.verticalCenter
            spacing: Th.space2

            TextField {
                id: valueField
                width: 140
                visible: optionRow.rowKind !== "header" && !optionRow.isBoolean
                anchors.verticalCenter: parent.verticalCenter
                text: optionRow.value
                placeholderText: optionRow.example
                color: optionRow.optionEnabled ? Th.text : Th.textMuted
                placeholderTextColor: Th.textDim
                font.pixelSize: Th.fontSmall
                background: Rectangle {
                    radius: Th.radiusControl
                    color: Th.surfaceAlt
                    border.width: 1
                    border.color: valueField.activeFocus ? Th.accent : Th.border
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }
                onTextEdited: {
                    optionList.importMessageCleared()
                    // Clearing the value also unticks the option: an enabled
                    // row with no value would build a broken "key =" line.
                    bridge.setOption(optionRow.optionKey, text !== "", text)
                    optionList.optionChanged()
                }
            }

            DarkSwitch {
                id: optionSwitch
                visible: optionRow.rowKind !== "header"
                anchors.verticalCenter: parent.verticalCenter
                checked: optionRow.optionEnabled
                onToggled: {
                    bridge.setOption(optionRow.optionKey, checked, valueField.text)
                    optionList.importMessageCleared()
                    optionList.optionChanged()
                }
            }
        }
    }
}
