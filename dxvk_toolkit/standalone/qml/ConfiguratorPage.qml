import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../ui/qml/theme.js" as Th
import "../../ui/qml" as Shared

// The standalone configurator's editor page.
//
// Same three-column shape as the full application's configuration page
// (categories | options | generated file), because the components are the
// same ones - only the meaning of the right-hand column differs: there it
// previews a file that will be written into a game folder, here it previews
// the file that is open and gets saved back.
Item {
    id: page
    objectName: "configuratorPage"

    property bool previewDirty: true
    property int selectedCount: 0
    property string importMessage: ""
    property string mode: {
        var saved = bridge.getSetting("config_mode")
        return (saved === "advanced" || saved === "full") ? saved : "simple"
    }
    property string currentSection: ""
    property var presetList: []

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

    readonly property int catalogueSize: configModel.count
    onCatalogueSizeChanged: page.previewDirty = true

    Component.onCompleted: {
        bridge.loadConfig()
        page.presetList = bridge.listPresets()
        page.applyDefaultPreview()
    }

    property bool previewInitialised: false
    property real previewWidth: 560

    function clampPreview(value) {
        var lower = 360
        var upper = Math.max(lower, page.width - 520)
        return Math.max(lower, Math.min(value, upper))
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

    // --- toolbar ---------------------------------------------------------
    Shared.ConfigToolbar {
        id: toolbar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        mode: page.mode
        importMessage: page.importMessage
        selectedCount: page.selectedCount
        // The file bar at the top of the window already opens .conf files.
        showImport: false
        onModeSelected: function (value) { page.setMode(value) }
        onSearchChanged: function (text) {
            bridge.filterConfig(text, page.mode, page.currentSection)
            page.previewDirty = true
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

    // --- context bar: presets and bulk actions ---------------------------
    Shared.ConfigContextBar {
        id: contextBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: toolbarLine.bottom
        // There is no "target" half here: the file that is open is the
        // target, and it is named in the window's file bar.
        showTarget: false
        presetList: page.presetList
        onPresetActivated: function (name) { bridge.applyPreset(name) }
        onSavePresetRequested: presetDialog.openWithName()
        onClearRequested: bridge.clearConfig()
    }

    // --- category rail ----------------------------------------------------
    Shared.ConfigRail {
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
    Shared.ConfigOptionList {
        id: optionList
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        anchors.left: rail.right
        anchors.right: divider.left
        // The full application's hint points at pages this tool does not
        // have; the reference file here is the bundled one.
        emptyText: qsTr("还没有可用的配置选项。\n请确认安装目录下有 assets/dxvk.conf，或在「参考文件」里指定一个 dxvk.conf。")
        onOptionChanged: page.previewDirty = true
        onImportMessageCleared: page.importMessage = ""
    }

    Rectangle {
        id: divider
        anchors.right: previewPane.left
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        width: 1
        color: dividerDrag.containsMouse || dividerDrag.pressed ? Th.accent : Th.borderSubtle
        Behavior on color { ColorAnimation { duration: 120 } }

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
                var pointer = mapToItem(page, mouse.x, mouse.y).x
                page.previewWidth = page.clampPreview(page.width - pointer)
            }
            onReleased: bridge.setSetting("config_preview_width",
                                          Math.round(page.previewWidth))
        }
    }

    // --- preview ----------------------------------------------------------
    Shared.ConfigPreviewPane {
        id: previewPane
        anchors.right: parent.right
        anchors.top: contextBar.bottom
        anchors.bottom: parent.bottom
        width: page.previewWidth
        // The target is the .conf file that is open, not a game folder.
        mode: "file"
        writeEnabled: bridge.hasFile()
        onRefreshRequested: page.refreshPreview()
        onWriteRequested: {
            bridge.saveFile()
            page.refreshPreview()
        }
    }

    Shared.ConfigPresetDialog {
        id: presetDialog
        descriptionText: qsTr("把当前勾选的所有选项保存为自定义预设，之后可在任意配置文件上一键套用。")
        builtInNoteText: qsTr("「性能优先」「兼容优先」「纯净」为内置预设，不可覆盖。")
        onPresetConfirmed: function (name) {
            bridge.savePreset(name)
            page.presetList = bridge.listPresets()
        }
    }
}
