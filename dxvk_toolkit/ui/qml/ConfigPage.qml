import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// Options on the left, the generated file on the right. The preview pane is
// part of the page (it was removed once and immediately missed): it shows the
// live result while options are ticked, and exports from its own buttons.
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

    // The option column keeps a readable measure; the preview takes the rest
    // and can be dragged wider from the divider.
    readonly property real maxOptionWidth: 860
    property real previewWidth: 560

    function clampPreview(value) {
        var lower = 360
        var upper = Math.max(lower, page.width - 520)
        return Math.max(lower, Math.min(value, upper))
    }

    Component.onCompleted: {
        bridge.loadConfig()
        var saved = bridge.getSetting("config_preview_width")
        page.previewWidth = page.clampPreview(
            (typeof saved === "number" && saved > 300) ? saved : page.width * 0.45)
    }

    onWidthChanged: page.previewWidth = page.clampPreview(page.previewWidth)

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
        interval: 300
        repeat: false
        running: page.previewDirty
        onTriggered: page.refreshPreview()
    }

    // The catalogue arrives asynchronously; without this the preview showed
    // "no reference file loaded" until the first option was ticked. A property
    // binding is used because QML cannot see a QAbstractListModel's
    // modelReset signal through Connections.
    readonly property int catalogueSize: configModel.count
    onCatalogueSizeChanged: page.previewDirty = true

    // --- custom tool tip --------------------------------------------------
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
            var point = row.mapToItem(page, 0, offsetY + 24)
            x = Math.max(Th.space4, Math.min(point.x + 48, page.width - width - Th.space4))
            y = Math.max(Th.space4, Math.min(point.y, page.height - height - Th.space4))
        }
    }

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
            spacing: Th.space2

            TextField {
                id: search
                width: 220
                anchors.verticalCenter: parent.verticalCenter
                placeholderText: "搜索选项…"
                color: Th.text
                placeholderTextColor: Th.textDim
                font.pixelSize: Th.fontSmall
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
                        color: parent.checked ? Th.accentDark
                             : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: parent.checked ? "#ffffff" : Th.textMuted
                        font.pixelSize: Th.fontSmall
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
                    font.pixelSize: Th.fontSmall
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
                  : "共 " + configModel.optionCount + " 项，已选 " + page.selectedCount
            color: page.importMessage !== "" ? Th.ok : Th.textMuted
            font.pixelSize: Th.fontCaption
            elide: Text.ElideRight
            width: Math.min(360, page.width * 0.3)
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

    // --- option list ------------------------------------------------------
    ListView {
        id: optionList
        objectName: "optionList"
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: divider.left
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
            onWheel: function (wheel) {
                var step = 58 * 3
                var delta = wheel.pixelDelta.y !== 0
                          ? wheel.pixelDelta.y * 2
                          : (wheel.angleDelta.y / 120) * step
                var limit = Math.max(0, optionList.contentHeight - optionList.height)
                optionList.contentY = Math.max(0, Math.min(limit, optionList.contentY - delta))
                wheel.accepted = true
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

            width: Math.min(optionList.width, page.maxOptionWidth)
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
                opacity: 0.5
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
                    color: check.checked ? Th.accentDark : Th.surfaceAlt
                    border.width: 1
                    border.color: check.checked
                                  ? Th.accent
                                  : (check.hovered ? Th.borderStrong : Th.border)

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Text {
                        anchors.centerIn: parent
                        text: "✓"
                        color: "#ffffff"
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
                    color: Th.textMuted
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
                font.pixelSize: Th.fontSmall
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
        anchors.right: preview.left
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom
        width: 1
        color: dividerDrag.containsMouse || dividerDrag.pressed ? Th.accent : Th.borderSubtle
        Behavior on color { ColorAnimation { duration: 120 } }

        // Grab area wider than the 1 px line; dragging moves the split.
        MouseArea {
            id: dividerDrag
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.leftMargin: -5
            anchors.rightMargin: -5
            hoverEnabled: true
            cursorShape: Qt.SplitHCursor
            preventStealing: true

            onPositionChanged: function (mouse) {
                if (!pressed)
                    return
                // Measured in page coordinates: the handle itself moves while
                // dragging, so its own local x would feed back on itself.
                var pointer = mapToItem(page, mouse.x, mouse.y).x
                page.previewWidth = page.clampPreview(page.width - pointer)
            }
            onReleased: bridge.setSetting("config_preview_width",
                                          Math.round(page.previewWidth))
        }
    }

    // --- preview ----------------------------------------------------------
    Item {
        id: preview
        objectName: "previewPane"
        anchors.right: parent.right
        anchors.top: toolbarLine.bottom
        anchors.bottom: parent.bottom
        width: page.previewWidth

        Rectangle {
            id: previewBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 52
            color: Th.surface

            Text {
                anchors.left: parent.left
                anchors.leftMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                text: "dxvk.conf 预览"
                color: Th.text
                font.pixelSize: Th.fontSubtitle
                font.bold: true
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: Th.space3
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
            color: Th.borderSubtle
        }

        Text {
            id: previewHint
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Th.space3
            height: 32
            text: "和游戏 exe 放在同一目录即可生效；这里可以独立导出，不需要扫描游戏。"
            color: Th.textDim
            font.pixelSize: Th.fontCaption
            wrapMode: Text.WordWrap
        }

        Flickable {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: previewLine.bottom
            anchors.bottom: previewHint.top
            anchors.leftMargin: Th.space3
            anchors.rightMargin: Th.space3
            anchors.topMargin: Th.space2
            clip: true
            contentWidth: previewArea.paintedWidth
            contentHeight: previewArea.paintedHeight
            boundsBehavior: Flickable.StopAtBounds

            TextArea {
                id: previewArea
                width: preview.width - Th.space5
                readOnly: true
                wrapMode: TextArea.NoWrap
                color: Th.text
                font.family: "Consolas"
                font.pixelSize: Th.fontSmall
                selectByMouse: true
                background: Rectangle { color: Th.surface }
            }
        }
    }
}
