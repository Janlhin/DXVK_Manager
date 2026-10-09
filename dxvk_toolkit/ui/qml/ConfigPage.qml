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

    // Editing target: "" is the shared default every game inherits, otherwise
    // a game key. The page stays in sync through onConfigTargetChanged below.
    property string gameKey: ""
    property string gameName: ""
    property string configStatus: "default"
    property string statusLabel: "默认配置"
    property string statusKind: "muted"
    property var presetList: []
    property var targetList: []
    // Mirror of the model's folded sections, only for the header arrows.
    property var collapsedSections: ({})

    function refreshStatus() {
        page.configStatus = bridge.gameConfigStatus(page.gameKey)
        if (page.gameKey === "") {
            page.statusLabel = "默认配置（所有游戏共用）"
            page.statusKind = "muted"
        } else if (page.configStatus === "written") {
            page.statusLabel = "已写入"
            page.statusKind = "ok"
        } else if (page.configStatus === "mismatch") {
            page.statusLabel = "与磁盘文件不同"
            page.statusKind = "warn"
        } else if (page.configStatus === "not-written") {
            page.statusLabel = "未写入"
            page.statusKind = "muted"
        } else {
            page.statusLabel = "状态未知"
            page.statusKind = "warn"
        }
    }

    function rebuildTargets() {
        var games = bridge.gameOptions()
        var list = [{ key: "", label: "默认配置（所有游戏共用）" }]
        for (var i = 0; i < games.length; i++)
            list.push({ key: games[i].key, label: games[i].label })
        page.targetList = list
        page.syncTargetPicker()
    }

    function syncTargetPicker() {
        for (var i = 0; i < page.targetList.length; i++)
            if (page.targetList[i].key === page.gameKey)
                targetPicker.currentIndex = i
    }

    function openForGame(key, name) {
        bridge.setConfigTarget(key, name)
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

    property bool previewInitialised: false

    Component.onCompleted: {
        bridge.loadConfig()
        page.presetList = bridge.listPresets()
        page.rebuildTargets()
        page.refreshStatus()
        // The window has no width yet while the component is being created,
        // so the default is taken again on the first resize.
        if (page.width > 0)
            page.applyDefaultPreview()
    }

    function applyDefaultPreview() {
        if (page.previewInitialised || page.width <= 0)
            return
        var saved = bridge.getSetting("config_preview_width")
        page.previewWidth = page.clampPreview(
            (typeof saved === "number" && saved > 300) ? saved : page.width * 0.45)
        page.previewInitialised = true
    }

    onWidthChanged: {
        page.applyDefaultPreview()
        page.previewWidth = page.clampPreview(page.previewWidth)
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

    Connections {
        target: bridge
        function onConfigTargetChanged(key, name) {
            page.gameKey = key
            page.gameName = name
            page.previewDirty = true
            page.syncTargetPicker()
            page.refreshStatus()
        }
        function onGamesReady(count) {
            page.rebuildTargets()
        }
    }

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

    component MiniButton: Button {
        id: mini
        padding: 6
        opacity: enabled ? 1.0 : 0.45
        background: Rectangle {
            radius: Th.radiusControl
            color: mini.hovered ? Th.surfaceHover : Th.surfaceAlt
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        contentItem: Text {
            text: mini.text
            color: Th.text
            font.pixelSize: Th.fontCaption
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
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
                onClicked: {
                    page.importMessage = bridge.importConfig()
                    page.previewDirty = true
                    page.refreshStatus()
                }
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

    // --- context bar: editing target, disk status, presets, bulk actions --
    Rectangle {
        id: contextBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: toolbarLine.bottom
        height: 46
        color: Th.surface

        Row {
            anchors.left: parent.left
            anchors.leftMargin: Th.pad
            anchors.verticalCenter: parent.verticalCenter
            spacing: Th.space2

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "作用对象"
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
            }

            ComboBox {
                id: targetPicker
                width: 240
                model: page.targetList
                textRole: "label"
                currentIndex: 0
                font.pixelSize: Th.fontSmall
                onActivated: {
                    var item = page.targetList[currentIndex]
                    if (item)
                        bridge.setConfigTarget(item.key, item.label)
                }
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
                text: page.statusLabel
                kind: page.statusKind
            }

            Item { width: Th.space3; height: 1 }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "预设"
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
            }

            ComboBox {
                id: presetPicker
                width: 150
                model: page.presetList
                currentIndex: -1
                font.pixelSize: Th.fontSmall
                displayText: currentIndex < 0 ? "选择预设…" : currentText
                onActivated: {
                    var name = page.presetList[currentIndex]
                    presetPicker.currentIndex = -1
                    if (name !== undefined && name !== "")
                        bridge.applyPreset(name)
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
                text: "存为预设"
                onClicked: {
                    presetNameField.text = ""
                    presetDialog.open()
                }
            }

            MiniButton {
                anchors.verticalCenter: parent.verticalCenter
                text: "清空"
                onClicked: bridge.clearConfig()
            }

            MiniButton {
                anchors.verticalCenter: parent.verticalCenter
                visible: page.gameKey !== ""
                text: "重置为默认"
                onClicked: bridge.resetConfigToDefault()
            }
        }
    }

    // --- option list ------------------------------------------------------
    ListView {
        id: optionList
        objectName: "optionList"
        anchors.top: contextBar.bottom
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

        Text {
            anchors.centerIn: parent
            visible: configModel.optionCount === 0
            width: Math.min(420, optionList.width - 48)
            text: "还没有可用的配置选项。\n先到「版本库」下载任意一个 DXVK 版本（自带参考文件），或到「设置」手动指定一个 dxvk.conf。"
            color: Th.textDim
            font.pixelSize: Th.fontBody
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
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
            required property string build

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

            // Header rows fold/unfold their section (rowHover ignores buttons).
            MouseArea {
                anchors.fill: parent
                enabled: optionRow.rowKind === "header"
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    var map = page.collapsedSections
                    if (map[optionRow.label])
                        delete map[optionRow.label]
                    else
                        map[optionRow.label] = true
                    page.collapsedSections = map
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
                text: page.collapsedSections[optionRow.label] ? "▸" : "▾"
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

            CheckBox {
                id: check
                visible: optionRow.rowKind !== "header"
                anchors.left: parent.left
                anchors.leftMargin: Th.space3
                anchors.verticalCenter: parent.verticalCenter
                checked: optionRow.optionEnabled
                onToggled: {
                    bridge.setOption(optionRow.optionKey, checked, valueField.text)
                    page.importMessage = ""
                    page.previewDirty = true
                }
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

                Row {
                    width: parent.width
                    spacing: Th.space2

                    Text {
                        text: optionRow.label + (optionRow.isBoolean ? "   · 开关" : "")
                        color: optionRow.optionEnabled ? Th.text : Th.textMuted
                        font.pixelSize: Th.fontSubtitle
                        font.bold: true
                        elide: Text.ElideRight
                        width: Math.min(implicitWidth, parent.width - forkBadge.width - Th.space2)
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
                            text: "GPLAsync 专有"
                            color: Th.warn
                            font.pixelSize: Th.fontMicro
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
                    // Clearing the value also unticks the option: an enabled
                    // row with no value would build a broken "key =" line.
                    bridge.setOption(optionRow.optionKey, text !== "", text)
                    page.previewDirty = true
                }
            }
        }
    }

    Rectangle {
        id: divider
        anchors.right: preview.left
        anchors.top: contextBar.bottom
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
        anchors.top: contextBar.bottom
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
                    id: writeButton
                    padding: 6
                    text: page.gameKey !== "" ? "应用并写入 " + page.gameName : "写入游戏…"
                    onClicked: {
                        if (page.gameKey !== "") {
                            bridge.writeConfToGame(page.gameKey)
                            page.refreshStatus()
                        } else {
                            gamePicker.open()
                        }
                    }
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

    // --- pick a game to write dxvk.conf into ------------------------------
    Dialog {
        id: gamePicker
        objectName: "gamePicker"
        modal: true
        anchors.centerIn: parent
        width: Math.min(page.width - 120, 560)
        height: Math.min(page.height - 120, 520)
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
                text: "把 dxvk.conf 写入哪个游戏？"
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
                        bridge.writeConfToGame(modelData.key)
                        gamePicker.close()
                    }
                }

                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: Th.space4
                    anchors.right: parent.right
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
                text: "写入前会把已有的 dxvk.conf 备份为 .bkp"
                color: Th.textDim
                font.pixelSize: Th.fontCaption
            }

            Button {
                anchors.right: parent.right
                anchors.rightMargin: Th.space4
                anchors.verticalCenter: parent.verticalCenter
                text: "关闭"
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

    // --- save the current selection as a named preset ----------------------
    Dialog {
        id: presetDialog
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
                text: "保存为预设"
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
                text: "把当前勾选的所有选项保存为自定义预设，之后可在任意游戏上一键套用。"
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
                wrapMode: Text.WordWrap
            }

            TextField {
                id: presetNameField
                width: presetDialog.availableWidth - Th.space6
                placeholderText: "预设名称，例如：赛博朋克专用"
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
                text: "「性能优先」「兼容优先」「纯净」为内置预设，不可覆盖。"
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
                    text: "保存"
                    padding: 6
                    onClicked: {
                        if (presetNameField.text.trim() !== "") {
                            bridge.savePreset(presetNameField.text)
                            page.presetList = bridge.listPresets()
                        }
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
                    text: "取消"
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
    }
}
