import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
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
    // Category rail selection: raw purpose/section key, "" shows all groups.
    property string currentSection: ""
    property string configStatus: "default"
    property string statusLabel: qsTr("默认配置")
    property string statusKind: "muted"
    property var presetList: []
    property var targetList: []
    // Mirror of the model's folded sections, only for the header arrows.
    property var collapsedSections: ({})

    function refreshStatus() {
        page.configStatus = bridge.gameConfigStatus(page.gameKey)
        if (page.gameKey === "") {
            page.statusLabel = qsTr("默认配置（所有游戏共用）")
            page.statusKind = "muted"
        } else if (page.configStatus === "written") {
            page.statusLabel = qsTr("已写入")
            page.statusKind = "ok"
        } else if (page.configStatus === "mismatch") {
            page.statusLabel = qsTr("与磁盘文件不同")
            page.statusKind = "warn"
        } else if (page.configStatus === "not-written") {
            page.statusLabel = qsTr("未写入")
            page.statusKind = "muted"
        } else {
            page.statusLabel = qsTr("状态未知")
            page.statusKind = "warn"
        }
    }

    function rebuildTargets() {
        var games = bridge.gameOptions()
        var list = [{ key: "", label: qsTr("默认配置（所有游戏共用）") }]
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
        bridge.filterConfig(search.text, value, page.currentSection)
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

    // §34 / T21: the sectioned documentation card behind the ⓘ badge. Three
    // parts (curated summary / example / raw upstream block), monospace code
    // blocks, scrollable and capped at 70% of the window - the long Reflex
    // style docs never fit a hover tip. Data comes from the row's doc role,
    // which the Python side fills from OptionGroup.doc_parts().
    Popup {
        id: docCard
        // Snapshot of the clicked row's fields: the delegate itself can be
        // destroyed by the list while the card is open (it scrolls away), so
        // holding the object reference would crash the bindings.
        property var row: null
        readonly property var doc: row && row.doc ? row.doc : ({})

        function openFor(target) {
            row = {"label": target.label, "optionKey": target.optionKey, "doc": target.doc || {}}
            open()
        }

        modal: true
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 560)
        height: Math.min(parent.height * 0.7, 620)
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#66000000" }
        background: Rectangle {
            radius: Th.radiusCard
            color: Th.surface
            border.width: 1
            border.color: Th.borderStrong
        }

        contentItem: ColumnLayout {
            spacing: 0

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Th.space4
                Layout.rightMargin: Th.space3
                Layout.topMargin: Th.space3
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: docCard.row ? docCard.row.label : ""
                        color: Th.text
                        font.pixelSize: Th.fontTitle
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "✕"
                        color: docClose.containsMouse ? Th.error : Th.textMuted
                        font.pixelSize: Th.fontBody

                        MouseArea {
                            id: docClose
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: docCard.close()
                        }
                    }
                }

                Text {
                    text: docCard.row ? docCard.row.optionKey : ""
                    color: Th.textMuted
                    font.family: "Consolas"
                    font.pixelSize: Th.fontCaption
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: docBody.implicitHeight + Th.space4 * 2
                boundsBehavior: Flickable.StopAtBounds
                clip: true

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: docBody
                    x: Th.space5
                    y: Th.space4
                    width: docCard.width - Th.space5 * 2
                    spacing: Th.space3

                    ColumnLayout {
                        visible: docCard.doc.summary !== ""
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: qsTr("说明")
                            color: Th.textMuted
                            font.pixelSize: Th.fontCaption
                            font.bold: true
                        }
                        Text {
                            text: docCard.doc.summary || ""
                            color: Th.text
                            font.pixelSize: Th.fontSmall
                            lineHeight: Th.lineHeight
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: qsTr("示例")
                            color: Th.textMuted
                            font.pixelSize: Th.fontCaption
                            font.bold: true
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            // Height from the content: a bare Rectangle would
                            // collapse to 0 and let the TextEdit overlap the
                            // next section.
                            implicitHeight: exampleText.implicitHeight + Th.space2 * 2
                            radius: Th.radiusSmall
                            color: Th.bg
                            border.width: 1
                            border.color: Th.border

                            TextEdit {
                                id: exampleText
                                x: Th.space3
                                y: Th.space2
                                width: parent.width - Th.space5
                                text: docCard.doc.example || ""
                                readOnly: true
                                selectByMouse: true
                                color: Th.accent
                                font.family: "Consolas"
                                font.pixelSize: Th.fontSmall
                                wrapMode: TextEdit.Wrap
                            }
                        }
                    }

                    ColumnLayout {
                        visible: docCard.doc.original !== ""
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: qsTr("DXVK 原文")
                            color: Th.textMuted
                            font.pixelSize: Th.fontCaption
                            font.bold: true
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: originalText.implicitHeight + Th.space2 * 2
                            radius: Th.radiusSmall
                            color: Th.bg
                            border.width: 1
                            border.color: Th.border

                            TextEdit {
                                id: originalText
                                x: Th.space3
                                y: Th.space2
                                width: parent.width - Th.space5
                                text: docCard.doc.original || ""
                                readOnly: true
                                selectByMouse: true
                                color: Th.text
                                font.family: "Consolas"
                                font.pixelSize: Th.fontSmall
                                wrapMode: TextEdit.Wrap
                            }
                        }
                    }
                }
            }
        }
    }

    // Same pill switch as the settings page (§29: both switches read and
    // write the same conf_comments key).
    component DarkSwitch: Switch {
        id: sw
        // 同 SettingsPage：Basic 样式 implicitWidth 不含 indicator，控件会
        // 塌缩到 padding*2，轨道向右溢出。钉死几何，Row 内占位才真实。
        implicitWidth: 40
        implicitHeight: 24
        padding: 0

        indicator: Rectangle {
            implicitWidth: 40
            implicitHeight: 22
            x: 0
            y: (sw.height - height) / 2
            radius: 11
            color: sw.checked ? Th.accentDark : Th.surfaceAlt
            border.width: 1
            border.color: sw.checked ? Th.accent : Th.border

            Behavior on color { ColorAnimation { duration: 120 } }

            Rectangle {
                width: 16
                height: 16
                radius: 8
                y: 2
                x: sw.checked ? parent.width - width - 3 : 3
                color: sw.checked ? "#ffffff" : Th.textMuted
                Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
        }
        contentItem: Item {}
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
                placeholderText: qsTr("搜索选项…")
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
                    bridge.filterConfig(text, page.mode, page.currentSection)
                    page.previewDirty = true
                }
            }

            Repeater {
                model: [
                    { value: "simple", label: qsTr("简单") },
                    { value: "advanced", label: qsTr("进阶") },
                    { value: "full", label: qsTr("完全") }
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
                text: qsTr("导入 dxvk.conf…")
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
                  : qsTr("共 %1 项，已选 %2").arg(configModel.optionCount).arg(page.selectedCount)
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
                text: qsTr("作用对象")
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
                // 默认目标下徽章文案与左侧下拉框完全重复；仅游戏目标时
                // 显示磁盘同步状态（已写入 / 与磁盘文件不同 / 未写入）。
                visible: page.gameKey !== ""
                text: page.statusLabel
                kind: page.statusKind
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
                model: page.presetList
                currentIndex: -1
                font.pixelSize: Th.fontSmall
                displayText: currentIndex < 0 ? qsTr("选择预设…") : currentText
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
                text: qsTr("存为预设")
                onClicked: {
                    presetNameField.text = ""
                    presetDialog.open()
                }
            }

            MiniButton {
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("清空")
                onClicked: bridge.clearConfig()
            }

            MiniButton {
                anchors.verticalCenter: parent.verticalCenter
                visible: page.gameKey !== ""
                text: qsTr("重置为默认")
                onClicked: bridge.resetConfigToDefault()
            }
        }
    }

    // --- category rail (direction C) --------------------------------------
    // 三栏布局的左栏：分类带计数（随搜索 + 难度实时变化），点击把列表
    // 过滤到该分类；再次点击或点「全部」恢复。key 用原始用途/section 名，
    // 与界面语言解耦；label 由模型按语言给出。
    Rectangle {
        id: rail
        anchors.left: parent.left
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        width: 148
        color: Th.surface

        Text {
            id: railTitle
            anchors.left: parent.left
            anchors.leftMargin: Th.space3
            anchors.top: parent.top
            anchors.topMargin: Th.space3
            text: qsTr("分类")
            color: Th.textMuted
            font.pixelSize: Th.fontCaption
            font.bold: true
        }

        Item {
            id: railAll
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: railTitle.bottom
            anchors.topMargin: Th.space2
            height: 30

            Rectangle {
                anchors.fill: parent
                anchors.margins: Th.space1
                radius: Th.radiusSmall
                color: page.currentSection === "" ? Th.accentDark
                       : (railAllHover.containsMouse ? Th.surfaceHover : "transparent")
            }
            MouseArea {
                id: railAllHover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    page.currentSection = ""
                    bridge.filterConfig(search.text, page.mode, "")
                    page.previewDirty = true
                }
            }
            Text {
                x: Th.space2
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("全部")
                color: page.currentSection === "" ? "#ffffff" : Th.text
                font.pixelSize: Th.fontSmall
                font.bold: page.currentSection === ""
            }
            Text {
                anchors.right: parent.right
                anchors.rightMargin: Th.space3
                anchors.verticalCenter: parent.verticalCenter
                text: configModel.optionCount
                color: page.currentSection === "" ? "#d7e3f8" : Th.textMuted
                font.pixelSize: Th.fontCaption
            }
        }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: railAll.bottom

            Repeater {
                model: configModel.sectionStats

                delegate: Item {
                    required property var modelData
                    width: parent.width
                    height: 30

                    readonly property bool active: page.currentSection === modelData.key

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: Th.space1
                        radius: Th.radiusSmall
                        color: parent.active ? Th.accentDark
                               : (railHover.containsMouse ? Th.surfaceHover : "transparent")
                    }
                    MouseArea {
                        id: railHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            page.currentSection = parent.active ? "" : parent.modelData.key
                            bridge.filterConfig(search.text, page.mode, page.currentSection)
                            page.previewDirty = true
                        }
                    }
                    Text {
                        x: Th.space2
                        width: parent.width - Th.space4 - 36
                        anchors.verticalCenter: parent.verticalCenter
                        text: parent.modelData.label
                        color: parent.active ? "#ffffff" : Th.text
                        font.pixelSize: Th.fontSmall
                        font.bold: parent.active
                        elide: Text.ElideRight
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: Th.space3
                        anchors.verticalCenter: parent.verticalCenter
                        text: parent.modelData.count
                        color: parent.active ? "#d7e3f8" : Th.textMuted
                        font.pixelSize: Th.fontCaption
                    }
                }
            }
        }
    }

    // --- option list ------------------------------------------------------
    ListView {
        id: optionList
        objectName: "optionList"
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        anchors.left: rail.right
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
                        page.importMessage = ""
                        // Clearing the value also unticks the option: an enabled
                        // row with no value would build a broken "key =" line.
                        bridge.setOption(optionRow.optionKey, text !== "", text)
                        page.previewDirty = true
                    }
                }

                DarkSwitch {
                    id: optionSwitch
                    visible: optionRow.rowKind !== "header"
                    anchors.verticalCenter: parent.verticalCenter
                    checked: optionRow.optionEnabled
                    onToggled: {
                        bridge.setOption(optionRow.optionKey, checked, valueField.text)
                        page.importMessage = ""
                        page.previewDirty = true
                    }
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
                id: previewTitle
                anchors.left: parent.left
                anchors.leftMargin: Th.space4
                // Bound to the controls row so longer interface languages
                // (English) elide the title instead of overlapping it.
                anchors.right: previewControls.left
                anchors.rightMargin: Th.space2
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: qsTr("dxvk.conf 预览")
                color: Th.text
                font.pixelSize: Th.fontSubtitle
                font.bold: true
            }

            Row {
                id: previewControls
                anchors.right: parent.right
                anchors.rightMargin: Th.space3
                anchors.verticalCenter: parent.verticalCenter
                spacing: Th.space2

                // §29: the comments toggle lives next to the result it
                // changes. getSetting returns undefined when the key was
                // never written, and the generator defaults it to True
                // (bridge.previewConfig), so treat "unset" as checked.
                Text {
                    text: qsTr("带注释")
                    color: Th.textMuted
                    font.pixelSize: Th.fontCaption
                    anchors.verticalCenter: parent.verticalCenter
                }
                DarkSwitch {
                    id: commentsSwitch
                    anchors.verticalCenter: parent.verticalCenter
                    checked: bridge.getSetting("conf_comments") !== false
                    onToggled: {
                        bridge.setSetting("conf_comments", checked)
                        page.refreshPreview()
                    }
                }

                Button {
                    text: qsTr("复制")
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
                    text: page.gameKey !== "" ? qsTr("应用并写入 %1").arg(page.gameName) : qsTr("写入游戏…")
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
                    text: qsTr("保存为文件…")
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
            text: qsTr("和游戏 exe 放在同一目录即可生效；这里可以独立导出，不需要扫描游戏。")
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
    }
}
