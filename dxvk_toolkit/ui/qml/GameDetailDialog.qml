import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// Per-game dialog, opened by double clicking a card. Modelled on DLSS
// Swapper's game page: artwork on the left, the facts and the pickers on the
// right, actions along the bottom. This is also the only place where DXVK can
// actually be applied to a game - the list itself only reports state.
Dialog {
    id: sheet
    objectName: "gameDetailDialog"

    property string gameKey: ""
    property string gameName: ""
    property string installPath: ""
    property string platformLabel: ""
    property string direct3d: ""
    property string arch: ""
    property string statusText: ""
    property string statusKind: "muted"
    property string coverUrl: ""

    property var versions: []        // kind -> locally installed names
    property var remote: []          // release dicts for the current kind, newest first
    property string kind: "dxvk"
    property string version: ""
    property string downloading: ""  // version currently auto-downloading
    property var versionRows: []      // rows shown in versionPicker, mirrored
                                     // off its model so the box can render
                                     // without reading model[currentIndex]
    property int versionCurrent: -1   // selected row index, mirrors
                                     // versionPicker.currentIndex

    readonly property var kindValues: ["dxvk", "gplasync"]
    readonly property var kindLabels: ["官方 DXVK", "DXVK-GPLAsync"]

    // A picked release is only applicable once it exists locally; gplasync
    // installs under the version without the leading "v".
    function installedHere(releaseVersion) {
        var display = sheet.kind === "gplasync" ? releaseVersion.replace(/^v/, "") : releaseVersion
        return (sheet.versions[sheet.kind] || []).indexOf(display) !== -1
    }

    readonly property bool versionInstalled: sheet.version !== "" && sheet.installedHere(sheet.version)

    function loadVersions() {
        bridge.loadLocalVersions()
        // The cached remote listing appears at once; a stale one refreshes
        // quietly in the background. The bridge slot is @Slot(str, bool) and
        // the Qt meta-object system cannot see Python default values, so both
        // arguments must be passed - a one-argument call is rejected with
        // "Error: Insufficient arguments" and the list silently never loads.
        bridge.loadVersions(sheet.kind, false)
    }

    // Combine the remote catalogue with the local cache: every downloadable
    // version is listed (DLSS Swapper style) and flagged with what is already
    // on disk. Locally installed versions survive a stale or empty remote list.
    function applyKind() {
        var rows = []
        var seen = {}
        for (var i = 0; i < sheet.remote.length; i++) {
            var name = String(sheet.remote[i].version || "")
            if (name === "" || seen[name])
                continue
            seen[name] = true
            rows.push({
                name: name,
                display: sheet.kind === "gplasync" ? name.replace(/^v/, "") : name,
                installed: sheet.installedHere(name)
            })
        }
        var installed = sheet.versions[sheet.kind] || []
        for (var j = 0; j < installed.length; j++) {
            var local = installed[j]
            var full = sheet.kind === "gplasync" ? "v" + local : local
            if (!seen[full])
                rows.push({ name: full, display: local, installed: true })
        }
        sheet.versionRows = rows
        versionPicker.model = rows
        // Default to the newest downloaded version, else the newest known one.
        var pick = -1
        for (var k = 0; k < rows.length; k++) {
            if (rows[k].installed) { pick = k; break }
        }
        if (pick < 0 && rows.length > 0)
            pick = 0
        sheet.versionCurrent = pick      // drives the box text; set right away so it
                                         // is correct even before the index lands
        sheet.version = pick >= 0 ? rows[pick].name : ""
        // Assigning model and currentIndex in the same tick makes Qt reset the
        // index to -1 (count is not settled yet); defer it to the next event
        // loop turn so the popup selection actually sticks.
        Qt.callLater(function() { versionPicker.currentIndex = pick })
    }

    modal: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 80, 880)
    height: Math.min(parent.height - 80, 560)
    padding: 0

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        color: Th.surface
        radius: Th.radiusPanel
        border.width: 1
        border.color: Th.borderStrong
    }

    Connections {
        target: bridge
        function onLocalVersionsReady(payload) {
            // downloadVersion emits this once its download finishes.
            sheet.downloading = ""
            sheet.versions = payload
            sheet.applyKind()
        }
        function onVersionsReady(payload) {
            if (payload.kind !== sheet.kind)
                return
            sheet.remote = payload.releases || []
            sheet.applyKind()
        }
        function onStatusMessage(text, kind) {
            if (kind === "error")
                sheet.downloading = ""   // a failed download frees the picker
        }
    }

    onOpened: sheet.loadVersions()

    contentItem: Rectangle {
        color: Th.surface

        RowLayout {
            anchors.fill: parent
            anchors.margins: Th.space5
            spacing: Th.space5

            // --- artwork ---------------------------------------------------
            Column {
                Layout.alignment: Qt.AlignTop
                spacing: Th.space2

                Rectangle {
                    width: 200
                    height: 300
                    radius: Th.radiusCard
                    color: Th.platformColor(sheet.platformLabel.toLowerCase())
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: sheet.coverUrl
                        asynchronous: true
                        fillMode: Image.PreserveAspectCrop
                        visible: status === Image.Ready
                    }
                    Text {
                        anchors.centerIn: parent
                        text: sheet.gameName.substring(0, 1).toUpperCase()
                        color: "#ffffff"
                        font.pixelSize: Th.fontDisplay
                        font.bold: true
                        visible: sheet.coverUrl === ""
                    }
                }
            }

            // --- facts and actions ------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Th.space4

                Text {
                    Layout.fillWidth: true
                    text: sheet.gameName
                    color: Th.text
                    font.pixelSize: Th.fontHeading
                    font.bold: true
                    wrapMode: Text.WordWrap
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Th.space1

                    Text { text: "安装路径"; color: Th.textMuted; font.pixelSize: Th.fontCaption }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Th.space2
                        TextField {
                            Layout.fillWidth: true
                            readOnly: true
                            text: sheet.installPath
                            color: Th.textMuted
                            font.pixelSize: Th.fontSmall
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: Th.surfaceAlt
                                border.width: 1
                                border.color: Th.border
                            }
                        }
                        Button {
                            text: "打开目录"
                            padding: 6
                            onClicked: bridge.openFolder(sheet.installPath)
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                            }
                            contentItem: Text {
                                text: parent.text; color: Th.text
                                font.pixelSize: Th.fontSmall
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                Row {
                    spacing: Th.space4

                    StatusChip {
                        anchors.verticalCenter: parent.verticalCenter
                        text: sheet.statusText
                        kind: sheet.statusKind
                    }

                    // "" only happens before detection has run; afterwards the
                    // bridge stores "Unknown" / "—" so the dialog stops saying
                    // 识别中 for a game that will never produce a value.
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (sheet.direct3d === "" ? "Direct3D 识别中…"
                               : (sheet.direct3d === "Unknown" ? "Direct3D 未知" : sheet.direct3d)) +
                              (sheet.arch !== "" ? "   ·   " + sheet.arch : "")
                        color: Th.textMuted
                        font.pixelSize: Th.fontCaption
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

                // --- pickers -------------------------------------------------
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Th.space4
                    rowSpacing: Th.space2

                    Text { text: "DXVK 来源"; color: Th.textMuted; font.pixelSize: Th.fontCaption }
                    Text { text: "版本"; color: Th.textMuted; font.pixelSize: Th.fontCaption }

                    ComboBox {
                        id: kindPicker
                        Layout.preferredWidth: 220
                        model: sheet.kindLabels
                        currentIndex: sheet.kindValues.indexOf(sheet.kind)
                        onActivated: {
                            sheet.kind = sheet.kindValues[currentIndex]
                            sheet.remote = []
                            sheet.applyKind()
                            bridge.loadVersions(sheet.kind, false)
                        }
                        font.pixelSize: Th.fontSmall
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: Th.surfaceAlt
                            border.width: 1
                            border.color: kindPicker.activeFocus ? Th.accent : Th.border
                        }
                        contentItem: Text {
                            leftPadding: Th.space3
                            text: kindPicker.displayText
                            color: Th.text
                            font.pixelSize: Th.fontSmall
                            verticalAlignment: Text.AlignVCenter
                        }
                        indicator: Text {
                            x: kindPicker.width - width - Th.space3
                            y: (kindPicker.height - height) / 2
                            text: "▾"
                            color: Th.textMuted
                            font.pixelSize: Th.fontSmall
                        }
                        popup: Popup {
                            y: kindPicker.height + 4
                            width: kindPicker.width
                            implicitHeight: contentItem.implicitHeight + Th.space2
                            padding: Th.space1
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: Th.surfaceAlt
                                border.width: 1
                                border.color: Th.borderStrong
                            }
                            contentItem: ListView {
                                implicitHeight: contentHeight
                                model: kindPicker.popup.visible ? kindPicker.delegateModel : null
                                clip: true
                                delegate: ItemDelegate {
                                    width: kindPicker.width - Th.space2
                                    contentItem: Text {
                                        text: modelData
                                        color: Th.text
                                        font.pixelSize: Th.fontSmall
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

                    ComboBox {
                        id: versionPicker
                        Layout.preferredWidth: 220
                        onActivated: {
                            var row = versionPicker.model[versionPicker.currentIndex]
                            if (!row)
                                return
                            sheet.versionCurrent = versionPicker.currentIndex
                            sheet.version = row.name
                            // Picking something that is not on disk downloads it
                            // first; the apply button unlocks when it arrives.
                            if (!row.installed && sheet.downloading === "") {
                                bridge.downloadVersion(sheet.kind, row.name)
                                sheet.downloading = row.name
                            }
                        }
                        font.pixelSize: Th.fontSmall
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: Th.surfaceAlt
                            border.width: 1
                            border.color: versionPicker.activeFocus ? Th.accent : Th.border
                        }
                        contentItem: Text {
                            leftPadding: Th.space3
                            text: {
                                var idx = sheet.versionCurrent
                                if (idx >= 0 && sheet.versionRows[idx]) {
                                    var row = sheet.versionRows[idx]
                                    var state = row.name === sheet.downloading ? " · 下载中…"
                                            : (row.installed ? " · 已下载" : " · 未下载")
                                    return row.display + state
                                }
                                return sheet.downloading !== "" ? sheet.downloading + "（下载中…）" : "（没有可用版本）"
                            }
                            color: sheet.versionCurrent >= 0 ? Th.text : Th.textDim
                            font.pixelSize: Th.fontSmall
                            verticalAlignment: Text.AlignVCenter
                        }
                        indicator: Text {
                            x: versionPicker.width - width - Th.space3
                            y: (versionPicker.height - height) / 2
                            text: "▾"
                            color: Th.textMuted
                            font.pixelSize: Th.fontSmall
                        }
                        popup: Popup {
                            y: versionPicker.height + 4
                            width: versionPicker.width
                            implicitHeight: Math.min(contentItem.implicitHeight + Th.space2, 240)
                            padding: Th.space1
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: Th.surfaceAlt
                                border.width: 1
                                border.color: Th.borderStrong
                            }
                            contentItem: ListView {
                                implicitHeight: contentHeight
                                model: versionPicker.popup.visible ? versionPicker.delegateModel : null
                                clip: true
                                delegate: ItemDelegate {
                                    width: versionPicker.width - Th.space2
                                    contentItem: Row {
                                        spacing: Th.space2
                                        Text {
                                            text: modelData.display
                                            color: Th.text
                                            font.pixelSize: Th.fontSmall
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        Text {
                                            text: modelData.name === sheet.downloading ? "下载中…"
                                                  : (modelData.installed ? "已下载" : "未下载 · 选后自动下载")
                                            color: modelData.installed ? Th.textMuted : Th.accent
                                            font.pixelSize: Th.fontCaption
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                    background: Rectangle {
                                        radius: Th.radiusControl - 2
                                        color: parent.hovered ? Th.surfaceHover : "transparent"
                                    }
                                }
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: {
                        var count = (sheet.versions[sheet.kind] || []).length
                        if (sheet.downloading !== "")
                            return "正在下载 " + sheet.downloading + " …完成后即可「应用 DXVK」，请稍候。"
                        if (sheet.remote.length === 0 && count === 0)
                            return "没有可用版本：离线且本地无缓存。联网后可到「版本库」点「强制刷新」。"
                        return "共 " + sheet.remote.length + " 个可下载版本，已下载 " + count +
                               " 个。选择未下载的版本会自动下载；应用时会自动备份原有 DLL（.bkp）。"
                    }
                    color: Th.textDim
                    font.pixelSize: Th.fontCaption
                    wrapMode: Text.WordWrap
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Th.space2

                    Button {
                        text: "应用 DXVK"
                        padding: 6
                        enabled: sheet.versionInstalled && sheet.downloading === ""
                        opacity: enabled ? 1.0 : 0.5
                        onClicked: {
                            bridge.installDxvk(sheet.gameKey, sheet.kind, sheet.version)
                            sheet.close()
                        }
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: !parent.enabled ? Th.surfaceAlt
                                 : (parent.hovered ? Th.primaryHover : Th.primary)
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.enabled ? Th.primaryText : Th.textDim
                            font.pixelSize: Th.fontSmall
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "DXVK 配置"
                        padding: 6
                        onClicked: {
                            // Switches the config editor to this game and the
                            // main window to the config page (bridge signal).
                            bridge.setConfigTarget(sheet.gameKey, sheet.gameName)
                            sheet.close()
                        }
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                        }
                        contentItem: Text {
                            text: parent.text; color: Th.text
                            font.pixelSize: Th.fontSmall
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "还原原始 DLL"
                        padding: 6
                        onClicked: { bridge.restoreGame(sheet.gameKey); sheet.close() }
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                        }
                        contentItem: Text {
                            text: parent.text; color: Th.text
                            font.pixelSize: Th.fontSmall
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "移除 DXVK"
                        padding: 6
                        onClicked: { bridge.removeDxvk(sheet.gameKey); sheet.close() }
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                        }
                        contentItem: Text {
                            text: parent.text; color: Th.text
                            font.pixelSize: Th.fontSmall
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "关闭"
                        padding: 6
                        onClicked: sheet.close()
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                        }
                        contentItem: Text {
                            text: parent.text; color: Th.textMuted
                            font.pixelSize: Th.fontSmall
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
    }
}
