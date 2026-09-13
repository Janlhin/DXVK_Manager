import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// One column of settings-style rows, capped at a readable measure. The
// generated file lives in a dialog: as a permanent right-hand pane it wasted
// half the window and squeezed the option list into two-line rows.
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

    readonly property real maxWidth: 920

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

    function openPreview() {
        page.refreshPreview()
        previewDialog.open()
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
            anchors.leftMargin: Math.max(Th.pad, (page.width - page.maxWidth) / 2)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Th.space2

            TextField {
                id: search
                width: 220
                anchors.verticalCenter: parent.verticalCenter
                placeholderText: "搜索选项…"
                color: Th.text
                placeholderTextColor: Th.textDim
                font.pixelSize: Th.fontBody
                background: Rectangle {
                    radius: Th.radiusControl
                    color: Th.surfaceAlt
                    border.width: 1
                    border.color: search.activeFocus ? Th.accent : Th.border
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }
                onTextChanged: {
                    bridge.filterConfig(text, page.mode)
                    page.previewDirty = true
                }
            }

            Repeater {
                model: [
                    { value: "simple", label: "简单" },
                    { value: "advanced", label: "进阶" },
                    { value: "full", label: "完全" }
                ]
                delegate: Button {
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    padding: 6
                    checkable: true
                    checked: page.mode === modelData.value
                    onClicked: page.setMode(modelData.value)
                    background: Rectangle {
                        radius: Th.radiusControl
                        color: parent.checked ? Th.primary
                             : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: parent.checked ? Th.primaryText : Th.textMuted
                        font.pixelSize: Th.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            Button {
                anchors.verticalCenter: parent.verticalCenter
                text: "导入 dxvk.conf…"
                padding: 6
                onClicked: page.importMessage = bridge.importConfig()
                background: Rectangle {
                    radius: Th.radiusControl
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

            Button {
                anchors.verticalCenter: parent.verticalCenter
                text: "预览并导出…"
                padding: 6
                onClicked: page.openPreview()
                background: Rectangle {
                    radius: Th.radiusControl
                    color: parent.hovered ? Th.primaryHover : Th.primary
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Text {
                    text: parent.text
                    color: Th.primaryText
                    font.pixelSize: Th.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        Text {
            anchors.right: parent.right
            anchors.rightMargin: Math.max(Th.pad, (page.width - page.maxWidth) / 2)
            anchors.verticalCenter: parent.verticalCenter
            text: page.importMessage !== ""
                  ? page.importMessage
                  : "共 " + configModel.optionCount + " 项，已选 " + page.selectedCount
            color: page.importMessage !== "" ? Th.ok : Th.textMuted
            font.pixelSize: Th.fontCaption
            elide: Text.ElideRight
            width: Math.min(320, page.width * 0.25)
            horizontalAlignment: Text.AlignRight
        }
    }

    Rectangle {
        id: toolbarLine
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: toolbar.bottom
        height: 1
        color: Th.borderSubtle
    }

    // --- options ---------------------------------------------------------
    ListView {
        id: optionList
        objectName: "optionList"
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(page.width, page.maxWidth)
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

        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function (event) {
                var delta = event.pixelDelta.y !== 0
                          ? event.pixelDelta.y * 2
                          : (event.angleDelta.y / 120) * 52 * 3
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
            height: optionRow.rowKind === "header" ? 40 : 58
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
                ToolTip.visible: containsMouse && optionRow.rowKind !== "header"
                                 && optionRow.description !== ""
                ToolTip.text: optionRow.description
                ToolTip.delay: 400
            }

            Text {
                visible: optionRow.rowKind === "header"
                anchors.left: parent.left
                anchors.leftMargin: Th.space4
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
                opacity: 0.55
            }

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

            Column {
                visible: optionRow.rowKind !== "header"
                anchors.left: parent.left
                anchors.leftMargin: 40
                anchors.right: valueField.visible ? valueField.left : parent.right
                anchors.rightMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1

                Text {
                    width: parent.width
                    text: optionRow.label + (optionRow.isBoolean ? "   · 开关" : "")
                    color: optionRow.optionEnabled ? Th.text : Th.textMuted
                    font.pixelSize: Th.fontSubtitle
                    font.bold: true
                    elide: Text.ElideRight
                }

                Text {
                    width: parent.width
                    visible: text !== ""
                    text: optionRow.summary
                    color: Th.textDim
                    font.pixelSize: Th.fontCaption
                    elide: Text.ElideRight
                }
            }

            TextField {
                id: valueField
                width: 120
                visible: optionRow.rowKind !== "header" && !optionRow.isBoolean
                anchors.right: parent.right
                anchors.rightMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                text: optionRow.value
                placeholderText: optionRow.example
                color: optionRow.optionEnabled ? Th.text : Th.textMuted
                placeholderTextColor: Th.textDim
                font.pixelSize: Th.fontBody
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

    // --- preview dialog ---------------------------------------------------
    Dialog {
        id: previewDialog
        objectName: "previewDialog"
        modal: true
        anchors.centerIn: parent
        width: Math.min(page.width - 80, 760)
        height: Math.min(page.height - 80, 620)
        padding: 0

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
                text: "dxvk.conf（已选 " + page.selectedCount + " 项）"
                color: Th.text
                font.pixelSize: Th.fontTitle
                font.bold: true
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: Th.space4
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
                        font.pixelSize: Th.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "保存为文件…"
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
                        font.pixelSize: Th.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "关闭"
                    padding: 6
                    onClicked: previewDialog.close()
                    background: Rectangle {
                        radius: Th.radiusControl
                        color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: Th.textMuted
                        font.pixelSize: Th.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        // A scrim behind the dialog, otherwise the page shows through.
        Overlay.modal: Rectangle { color: "#99000000" }

        contentItem: Item {
            Rectangle {
                anchors.fill: parent
                color: Th.surface
            }

            Flickable {
            anchors.fill: parent
            clip: true
            contentWidth: previewArea.paintedWidth
            contentHeight: previewArea.paintedHeight
            boundsBehavior: Flickable.StopAtBounds

            TextArea {
                id: previewArea
                width: previewDialog.width - Th.space5
                readOnly: true
                wrapMode: TextArea.NoWrap
                color: Th.text
                font.family: "Consolas"
                font.pixelSize: Th.fontBody
                selectByMouse: true
                background: Rectangle { color: Th.surface }
            }
            }
        }

        footer: Item {
            height: 40

            Text {
                anchors.left: parent.left
                anchors.leftMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                text: "放在游戏 exe 同级目录即可生效。"
                color: Th.textDim
                font.pixelSize: Th.fontCaption
            }
        }
    }
}
