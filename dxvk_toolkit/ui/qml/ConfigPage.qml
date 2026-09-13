import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// Layout uses plain anchors on purpose: a view that is a direct child of a
// QtQuick Layout never populated its delegates here, while anchored views do.
Item {
    id: page
    objectName: "configPage"

    property bool previewDirty: true
    property int selectedCount: 0
    property string importMessage: ""
    property string mode: {
        var saved = bridge.getSetting("config_mode")
        return (saved === "advanced" || saved === "full") ? saved : "simple"
    }

    function setMode(value) {
        page.mode = value
        bridge.setSetting("config_mode", value)
        bridge.filterConfig(search.text, value)
        page.previewDirty = true
    }

    function refreshPreview() {
        previewArea.text = bridge.previewConfig()
        page.selectedCount = bridge.selectedOptionCount()
        page.previewDirty = false
    }

    Timer {
        interval: 280
        repeat: false
        running: page.previewDirty
        onTriggered: page.refreshPreview()
    }

    Component.onCompleted: bridge.loadConfig()

    // --- toolbar ---------------------------------------------------------
    Rectangle {
        id: toolbar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 52
        color: Th.surface

        Row {
            anchors.left: parent.left
            anchors.leftMargin: Th.pad
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            TextField {
                id: search
                width: 220
                placeholderText: "搜索选项…"
                color: Th.text
                placeholderTextColor: Th.textDim
                background: Rectangle {
                    radius: Th.radiusSmall
                    color: Th.surfaceAlt
                    border.color: search.activeFocus ? Th.accent : Th.border
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }
                onTextChanged: {
                    bridge.filterConfig(text, page.mode)
                    page.previewDirty = true
                }
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Repeater {
                    model: [
                        { value: "simple", label: "简单" },
                        { value: "advanced", label: "进阶" },
                        { value: "full", label: "完全" }
                    ]
                    delegate: Button {
                        text: modelData.label
                        checkable: true
                        checked: page.mode === modelData.value
                        onClicked: page.setMode(modelData.value)
                        background: Rectangle {
                            radius: Th.radiusSmall
                            color: parent.checked ? Th.accentDark
                                 : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? "#ffffff" : Th.textMuted
                            font.pixelSize: Th.fontBody
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            Button {
                anchors.verticalCenter: parent.verticalCenter
                text: "导入 dxvk.conf…"
                onClicked: page.importMessage = bridge.importConfig()
                background: Rectangle {
                    radius: Th.radiusSmall
                    color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Text {
                    text: parent.text
                    color: Th.text
                    font.pixelSize: Th.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        Text {
            anchors.right: parent.right
            anchors.rightMargin: Th.pad
            anchors.verticalCenter: parent.verticalCenter
            text: page.importMessage !== ""
                  ? page.importMessage
                  : "共 " + configModel.count + " 项，已选 " + page.selectedCount
            color: page.importMessage !== "" ? Th.ok : Th.textDim
            font.pixelSize: Th.fontCaption
        }
    }

    Rectangle {
        id: toolbarLine
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: toolbar.bottom
        height: 1
        color: Th.border
    }

    // --- option list -----------------------------------------------------
    ListView {
        id: optionList
        objectName: "optionList"
        anchors.left: parent.left
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom
        width: Math.round(page.width * 0.56)
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
                              duration: 180; easing.type: Easing.OutCubic }
        }

        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function (event) {
                var delta = event.pixelDelta.y !== 0
                          ? event.pixelDelta.y * 2
                          : (event.angleDelta.y / 120) * 46 * 3
                var limit = Math.max(0, optionList.contentHeight - optionList.height)
                optionList.contentY = Math.max(0, Math.min(limit, optionList.contentY - delta))
                event.accepted = true
            }
        }

delegate: Rectangle {
            id: optionRow
            required property int index
            required property string rowKind
            required property string optionKey
            required property string label
            required property string description
            required property string summary
            required property string example
            required property bool optionEnabled
            required property bool isBoolean
            required property string value

            width: optionList.width
            height: optionRow.rowKind === "header"
                    ? 32
                    : (optionRow.summary !== "" ? 64 : 44)
            color: optionRow.rowKind === "header"
                   ? Th.surfaceAlt
                   : (rowHover.containsMouse ? Th.surfaceHover
                                             : (index % 2 === 0 ? Th.bg : Th.surface))

            Behavior on color { ColorAnimation { duration: 120 } }

            MouseArea {
                id: rowHover
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
                ToolTip.visible: containsMouse && optionRow.rowKind !== "header"
                                 && optionRow.description !== ""
                ToolTip.text: optionRow.description
                ToolTip.delay: 400
            }

            // --- section header -------------------------------------------
            Text {
                visible: optionRow.rowKind === "header"
                anchors.left: parent.left
                anchors.leftMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                text: optionRow.label
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
                font.bold: true
                font.letterSpacing: 0.5
            }

            // --- control, pinned to the right edge like a settings row -----
            CheckBox {
                id: check
                visible: optionRow.rowKind !== "header"
                anchors.left: parent.left
                anchors.leftMargin: Th.space3
                anchors.verticalCenter: parent.verticalCenter
                checked: optionRow.optionEnabled
                onToggled: bridge.setOption(optionRow.optionKey, checked, valueField.text)
                contentItem: Item {}

                indicator: Rectangle {
                    implicitWidth: 16
                    implicitHeight: 16
                    x: check.leftPadding
                    y: check.height / 2 - height / 2
                    radius: Th.radiusMicro
                    color: check.checked ? Th.primary : Th.surfaceAlt
                    border.width: 1
                    border.color: check.checked
                                  ? Th.primaryHover
                                  : (check.hovered ? Th.borderStrong : Th.border)

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Text {
                        anchors.centerIn: parent
                        text: "✓"
                        color: Th.primaryText
                        font.pixelSize: Th.fontCaption
                        font.bold: true
                        visible: check.checked
                    }
                }
            }

            // --- text block -------------------------------------------------
            Column {
                visible: optionRow.rowKind !== "header"
                anchors.left: parent.left
                anchors.leftMargin: 40
                anchors.right: valueField.visible ? valueField.left : parent.right
                anchors.rightMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Row {
                    width: parent.width
                    spacing: Th.space2

                    Text {
                        text: optionRow.label
                        color: optionRow.optionEnabled ? Th.text : Th.textMuted
                        font.pixelSize: Th.fontBody
                        font.bold: optionRow.optionEnabled
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: optionRow.isBoolean
                        text: "开关"
                        color: Th.textDim
                        font.pixelSize: Th.fontMicro
                    }
                }

                Text {
                    width: parent.width
                    visible: text !== ""
                    text: optionRow.summary
                    color: Th.textMuted
                    font.pixelSize: Th.fontCaption
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }

            // --- value field, at the right end of the row -------------------
            TextField {
                id: valueField
                width: 120
                visible: optionRow.rowKind !== "header" && !optionRow.isBoolean
                anchors.right: parent.right
                anchors.rightMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                text: optionRow.value
                placeholderText: optionRow.example
                color: optionRow.optionEnabled ? Th.text : Th.textDim
                placeholderTextColor: Th.textDim
                font.pixelSize: Th.fontCaption
                background: Rectangle {
                    radius: Th.radiusControl
                    color: Th.surfaceAlt
                    border.width: 1
                    border.color: valueField.activeFocus ? Th.accent : Th.border
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }
                onTextEdited: {
                    page.importMessage = ""
                    bridge.setOption(optionRow.optionKey, true, text)
                }
            }
        }
    }
    Rectangle {
        id: divider
        anchors.left: optionList.right
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom
        width: 1
        color: Th.border
    }

    // --- preview ---------------------------------------------------------
    Item {
        id: previewPane
        anchors.left: divider.right
        anchors.right: parent.right
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom

        Rectangle {
            id: previewBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 48
            color: Th.surface

            Text {
                anchors.left: parent.left
                anchors.leftMargin: Th.pad
                anchors.verticalCenter: parent.verticalCenter
                text: "dxvk.conf 预览"
                color: Th.text
                font.pixelSize: Th.fontBody
                font.bold: true
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: Th.pad
                anchors.verticalCenter: parent.verticalCenter
                spacing: Th.space2

                Button {
                    text: "复制"
                    padding: 6
                    onClicked: bridge.copyConfig()
                    background: Rectangle {
                        radius: Th.radiusControl
                        color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: Th.text
                        font.pixelSize: Th.fontCaption
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "导出为文件…"
                    padding: 6
                    onClicked: bridge.exportConfig()
                    background: Rectangle {
                        radius: Th.radiusControl
                        color: parent.hovered ? Th.primaryHover : Th.primary
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: Th.primaryText
                        font.pixelSize: Th.fontCaption
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        Rectangle {
            id: previewLine
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: previewBar.bottom
            height: 1
            color: Th.border
        }

        Text {
            id: previewHint
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Th.space3
            height: 32
            text: "dxvk.conf 要和游戏 exe 放在同一目录；这里可以独立导出，不需要扫描游戏。"
            color: Th.textDim
            font.pixelSize: Th.fontCaption
            wrapMode: Text.WordWrap
        }

        Flickable {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: previewLine.bottom
            anchors.bottom: previewHint.top
            anchors.bottomMargin: Th.space1
            clip: true
            contentWidth: previewArea.paintedWidth
            contentHeight: previewArea.paintedHeight
            boundsBehavior: Flickable.StopAtBounds

            TextArea {
                id: previewArea
                width: previewPane.width - Th.space5
                readOnly: true
                wrapMode: TextArea.NoWrap
                color: Th.text
                font.family: "Consolas"
                font.pixelSize: Th.fontCaption
                selectByMouse: true
                background: Rectangle { color: Th.surface }
            }
        }
    }
}