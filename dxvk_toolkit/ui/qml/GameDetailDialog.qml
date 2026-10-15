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
    property string platform: ""      // raw source key, drives the color only
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
    property var fp: ({})             // DXVK fingerprint payload (bridge)

    readonly property var kindValues: ["dxvk", "gplasync"]
    readonly property var kindLabels: [qsTr("官方 DXVK"), "DXVK-GPLAsync"]

    // A picked release is only applicable once it exists locally; gplasync
    // installs under the version without the leading "v".
    function installedHere(releaseVersion) {
        var display = sheet.kind === "gplasync" ? releaseVersion.replace(/^v/, "") : releaseVersion
        return (sheet.versions[sheet.kind] || []).indexOf(display) !== -1
    }

    readonly property bool versionInstalled: sheet.version !== "" && sheet.installedHere(sheet.version)

    readonly property bool fpHasDxvk: (sheet.fp.dllNames || []).length > 0
    readonly property bool fpShow: sheet.fpHasDxvk && !sheet.fp.managed
    readonly property string fpVerdict: {
        if (!sheet.fpHasDxvk)
            return ""
        var names = (sheet.fp.dllNames || []).join(" + ")
        if (sheet.fp.official)
            return qsTr("已装 %1（%2）· 哈希与官方缓存一致，未经修改").arg(sheet.fp.version || "?").arg(names)
        if (sheet.fp.version !== "")
            return qsTr("已装 DXVK v%1（%2）· 与本地缓存不符：魔改或非官方构建，也可能是本地未下载该版本").arg(sheet.fp.version).arg(names)
        return qsTr("已装 DXVK（%1）· 二进制未带版本标记，无法核对来源").arg(names)
    }

    function loadVersions() {
        bridge.loadLocalVersions()
        // The cached remote listing appears at once; a stale one refreshes
        // quietly in the background. The bridge slot is @Slot(str, bool) and
        // the Qt meta-object system cannot see Python default values, so both
        // arguments must be passed - a one-argument call is rejected with
        // "Error: Insufficient arguments" and the list silently never loads.
        bridge.loadVersions(sheet.kind, false)
    }

    // Combine the remote catalogue with the local cache. Downloaded versions
    // sort into their own group ABOVE the not-downloaded ones (each group
    // newest first) - a mixed order made the blue "pick to auto-download"
    // rows drown the ones that are ready to apply.
    function applyKind() {
        var downloadedRows = []
        var pendingRows = []
        var seen = {}
        for (var i = 0; i < sheet.remote.length; i++) {
            var name = String(sheet.remote[i].version || "")
            if (name === "" || seen[name])
                continue
            seen[name] = true
            var installed = sheet.installedHere(name)
            var row = {
                name: name,
                display: sheet.kind === "gplasync" ? name.replace(/^v/, "") : name,
                installed: installed
            }
            if (installed)
                downloadedRows.push(row)
            else
                pendingRows.push(row)
        }
        var locals = sheet.versions[sheet.kind] || []
        for (var j = 0; j < locals.length; j++) {
            var local = locals[j]
            var full = sheet.kind === "gplasync" ? "v" + local : local
            if (!seen[full])
                downloadedRows.push({ name: full, display: local, installed: true })
        }
        var rows = downloadedRows.concat(pendingRows)
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
        function onFingerprintReady(key, payload) {
            if (key === sheet.gameKey)
                sheet.fp = payload
        }
    }

    onOpened: {
        sheet.loadVersions()
        sheet.fp = {}
        bridge.requestFingerprint(sheet.gameKey)
    }

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
                    color: Th.platformColor(sheet.platform.toLowerCase())
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

                    Text { text: qsTr("安装路径"); color: Th.textMuted; font.pixelSize: Th.fontCaption }
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
                            text: qsTr("打开目录")
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
                        text: (sheet.direct3d === "" ? qsTr("Direct3D 识别中…")
                               : (sheet.direct3d === "Unknown" ? qsTr("Direct3D 未知") : sheet.direct3d)) +
                              (sheet.arch !== "" ? "   ·   " + sheet.arch : "")
                        color: Th.textMuted
                        font.pixelSize: Th.fontCaption
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

                // --- fingerprint / takeover ----------------------------------
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Th.space2
                    visible: sheet.fpShow || (sheet.fpHasDxvk && sheet.fp.managed && sheet.fp.version !== "")

                    Text {
                        Layout.fillWidth: true
                        visible: sheet.fpHasDxvk
                        text: sheet.fpVerdict
                        color: sheet.fp.official ? Th.ok : (sheet.fpShow ? Th.warn : Th.textDim)
                        font.pixelSize: Th.fontCaption
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        spacing: Th.space2
                        visible: sheet.fpShow

                        Button {
                            text: qsTr("接管此安装")
                            padding: 6
                            onClicked: { bridge.adoptDxvk(sheet.gameKey, false); sheet.close() }
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: parent.hovered ? Th.primaryHover : Th.primary
                            }
                            contentItem: Text {
                                text: parent.text; color: Th.primaryText
                                font.pixelSize: Th.fontSmall
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Button {
                            text: qsTr("接管并补还原点")
                            padding: 6
                            onClicked: { bridge.adoptDxvk(sheet.gameKey, true); sheet.close() }
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: parent.hovered ? Th.okHover : Th.ok
                            }
                            contentItem: Text {
                                text: parent.text; color: Th.primaryText
                                font.pixelSize: Th.fontSmall
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: sheet.fpShow
                        text: qsTr("接管后此 DXVK 归本工具管理：显示版本、可直接升级；还原点从 Windows 系统目录补建（并非游戏原始文件）。")
                        color: Th.textMuted
                        font.pixelSize: Th.fontMicro
                        wrapMode: Text.WordWrap
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle; visible: sheet.fpShow }

                // --- pickers -------------------------------------------------
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Th.space4
                    rowSpacing: Th.space2

                    Text { text: qsTr("DXVK 来源"); color: Th.textMuted; font.pixelSize: Th.fontCaption }
                    Text { text: qsTr("版本"); color: Th.textMuted; font.pixelSize: Th.fontCaption }

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
                                    var state = row.name === sheet.downloading ? qsTr(" · 下载中…")
                                            : (row.installed ? qsTr(" · 已下载") : qsTr(" · 未下载"))
                                    return row.display + state
                                }
                                return sheet.downloading !== "" ? sheet.downloading + qsTr("（下载中…）") : qsTr("（没有可用版本）")
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
                                            text: modelData.name === sheet.downloading ? qsTr("下载中…")
                                                  : (modelData.installed ? qsTr("已下载") : qsTr("未下载 · 选后自动下载"))
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
                            return qsTr("正在下载 %1 …完成后即可「应用 DXVK」，请稍候。").arg(sheet.downloading)
                        if (sheet.remote.length === 0 && count === 0)
                            return qsTr("没有可用版本：离线且本地无缓存。联网后可到「版本库」点「强制刷新」。")
                        return qsTr("共 %1 个可下载版本，已下载 %2 个。选择未下载的版本会自动下载；应用时会自动备份原有 DLL（.bkp）。")
                               .arg(sheet.remote.length).arg(count)
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
                        text: qsTr("应用 DXVK")
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
                        text: qsTr("DXVK 配置")
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
                        text: qsTr("还原原始 DLL")
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
                        text: qsTr("移除 DXVK")
                        padding: 6
                        onClicked: removeConfirm.open()
                        background: Rectangle {
                            radius: Th.radiusControl
                            color: parent.hovered ? Th.errorHover : Th.error
                        }
                        contentItem: Text {
                            text: parent.text; color: Th.primaryText
                            font.pixelSize: Th.fontSmall
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: qsTr("关闭")
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

    // Removing DXVK touches files this tool created (and, for foreign
    // installs, files the user brought) - one confirm, with a checkbox for
    // the companion files, is cheaper than a surprise either way.
    Dialog {
        id: removeConfirm
        modal: true
        anchors.centerIn: parent
        width: Math.min(parent.width - 120, 460)
        padding: Th.space5
        Overlay.modal: Rectangle { color: "#99000000" }
        background: Rectangle {
            radius: Th.radiusCard
            color: Th.surface
            border.width: 1
            border.color: Th.border
        }

        contentItem: ColumnLayout {
            spacing: Th.space3

            Text {
                text: sheet.fpShow ? qsTr("移除未接管的 DXVK？") : qsTr("移除 DXVK？")
                color: Th.text
                font.pixelSize: Th.fontTitle
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Text {
                text: {
                    if (sheet.fpShow)
                        return qsTr("这套 DXVK 不是本工具安装的，移除后无法通过本工具还原。")
                             + (sheet.fp.version !== ""
                                ? "\n" + qsTr("即将删除：DXVK v%1。").arg(sheet.fp.version)
                                : "")
                    if (sheet.fp.version !== "")
                        return qsTr("即将从游戏目录删除 DXVK v%1 并清除接管记录。").arg(sheet.fp.version)
                    return qsTr("即将从游戏目录删除 DXVK 并清除接管记录。")
                }
                color: Th.textMuted
                font.pixelSize: Th.fontSmall
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            CheckBox {
                id: artifactsBox
                text: qsTr("同时清理 dxvk.conf、DXVK 日志与着色器缓存")
                checked: true
                font.pixelSize: Th.fontSmall
                contentItem: Text {
                    text: artifactsBox.text
                    color: Th.text
                    font.pixelSize: Th.fontSmall
                    leftPadding: artifactsBox.indicator.width + artifactsBox.spacing
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                }
                indicator: Rectangle {
                    x: artifactsBox.leftPadding
                    y: artifactsBox.height / 2 - height / 2
                    width: 16
                    height: 16
                    radius: 3
                    color: artifactsBox.checked ? Th.primary : Th.surfaceAlt
                    border.width: 1
                    border.color: artifactsBox.checked ? Th.primary : Th.borderStrong
                    Text {
                        anchors.centerIn: parent
                        text: artifactsBox.checked ? "✓" : ""
                        color: Th.primaryText
                        font.pixelSize: 11
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Th.space2

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("取消")
                    padding: 6
                    onClicked: removeConfirm.close()
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
                    text: qsTr("仍要移除")
                    padding: 6
                    onClicked: {
                        removeConfirm.close()
                        bridge.removeDxvk(sheet.gameKey, artifactsBox.checked)
                        sheet.close()
                    }
                    background: Rectangle {
                        radius: Th.radiusControl
                        color: parent.hovered ? Th.errorHover : Th.error
                    }
                    contentItem: Text {
                        text: parent.text; color: Th.primaryText
                        font.pixelSize: Th.fontSmall
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
    }
}
