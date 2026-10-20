import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// Options on the left, the generated file on the right. The preview pane is
// part of the page (it was removed once and immediately missed): it shows the
// live result while options are ticked, and exports from its own buttons.
//
// This file is the page's wiring only: every visible part lives in its own
// component (ConfigToolbar, ConfigContextBar, ConfigRail, ConfigOptionList,
// ConfigPreviewPane, ConfigGamePicker, ConfigPresetDialog), so each one can
// be loaded and checked on its own - see tests/qml_components.py.
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
                contextBar.targetIndex = i
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
        bridge.filterConfig(toolbar.searchText, value, page.currentSection)
        page.previewDirty = true
    }

    function refreshPreview() {
        previewPane.refresh(bridge.previewConfig())
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

    // --- toolbar ---------------------------------------------------------
    ConfigToolbar {
        id: toolbar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        mode: page.mode
        importMessage: page.importMessage
        selectedCount: page.selectedCount
        onModeSelected: function (value) { page.setMode(value) }
        onSearchChanged: function (text) {
            bridge.filterConfig(text, page.mode, page.currentSection)
            page.previewDirty = true
        }
        onImportRequested: {
            page.importMessage = bridge.importConfig()
            page.previewDirty = true
            page.refreshStatus()
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
    ConfigContextBar {
        id: contextBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: toolbarLine.bottom
        targetList: page.targetList
        targetIndex: 0
        presetList: page.presetList
        statusLabel: page.statusLabel
        statusKind: page.statusKind
        gameKey: page.gameKey
        showStatus: page.gameKey !== ""
        onTargetActivated: function (index) {
            var item = page.targetList[index]
            if (item)
                bridge.setConfigTarget(item.key, item.label)
        }
        onPresetActivated: function (name) { bridge.applyPreset(name) }
        onSavePresetRequested: presetDialog.openWithName()
        onClearRequested: bridge.clearConfig()
        onResetRequested: bridge.resetConfigToDefault()
    }

    // --- category rail (direction C) --------------------------------------
    // 三栏布局的左栏：分类带计数（随搜索 + 难度实时变化），点击把列表
    // 过滤到该分类；再次点击或点「全部」恢复。key 用原始用途/section 名，
    // 与界面语言解耦；label 由模型按语言给出。
    ConfigRail {
        id: rail
        anchors.left: parent.left
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        currentSection: page.currentSection
        onSectionSelected: function (section) {
            page.currentSection = section
            bridge.filterConfig(toolbar.searchText, page.mode, section)
            page.previewDirty = true
        }
    }

    // --- option list ------------------------------------------------------
    ConfigOptionList {
        id: optionList
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        anchors.left: rail.right
        anchors.right: divider.left
        onOptionChanged: page.previewDirty = true
        onImportMessageCleared: page.importMessage = ""
        onCollapsedSectionsChanged: page.collapsedSections = collapsedSections
    }

    Rectangle {
        id: divider
        anchors.right: previewPane.left
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
    ConfigPreviewPane {
        id: previewPane
        anchors.right: parent.right
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        width: page.previewWidth
        gameKey: page.gameKey
        gameName: page.gameName
        onRefreshRequested: page.refreshPreview()
        onWriteRequested: {
            bridge.writeConfToGame(page.gameKey)
            page.refreshStatus()
        }
        onGamePickerRequested: gamePicker.open()
    }

    // --- pick a game to write dxvk.conf into ------------------------------
    ConfigGamePicker {
        id: gamePicker
        onGameChosen: function (key) {
            bridge.writeConfToGame(key)
        }
    }

    // --- save the current selection as a named preset ----------------------
    ConfigPresetDialog {
        id: presetDialog
        onPresetConfirmed: function (name) {
            bridge.savePreset(name)
            page.presetList = bridge.listPresets()
        }
    }
}
