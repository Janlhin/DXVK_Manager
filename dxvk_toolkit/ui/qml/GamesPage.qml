import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The library. One toolbar (search, one filter button, add, scan), then either
// a wall of cover cards or a list, both split into 已装 DXVK / 未安装 sections.
// Clicking a game opens its dialog - there is no separate details bar, which
// used to eat the bottom of the window and duplicate what the dialog shows.
Item {
    id: page
    objectName: "gamesPage"

    property string filterPlatform: ""
    property var platformOptions: []
    property string viewMode: bridge.getSetting("games_view") === "list" ? "list" : "grid"
    property string dxtkFilter: {
        var saved = bridge.getSetting("games_dxtk_filter")
        return (saved === "patched" || saved === "clean") ? saved : "all"
    }
    property var dxtkCounts: ({"all": 0, "patched": 0, "clean": 0})

    function dxtkCount(value) {
        return page.dxtkCounts[value] !== undefined ? page.dxtkCounts[value] : 0
    }

    function platformLabel(value) {
        for (var i = 0; i < page.platformOptions.length; i++) {
            if (page.platformOptions[i].value === value)
                return page.platformOptions[i].label
        }
        return ""
    }

    // What the 筛选 button shows, so the current narrowing is visible without
    // opening the panel.
    function filterSummary() {
        var parts = []
        if (page.dxtkFilter === "patched")
            parts.push(qsTr("已装 DXVK"))
        else if (page.dxtkFilter === "clean")
            parts.push(qsTr("未安装"))
        if (page.filterPlatform !== "")
            parts.push(page.platformLabel(page.filterPlatform))
        if (parts.length === 0)
            return qsTr("筛选")
        return qsTr("筛选：%1").arg(parts.join(" · "))
    }

    function applyFilters() {
        bridge.setFilter(search.text, page.filterPlatform, page.dxtkFilter)
        Qt.callLater(page.requestVisible)
    }

    function setDxtkFilter(value) {
        page.dxtkFilter = value
        bridge.setSetting("games_dxtk_filter", value)
        page.applyFilters()
    }

    function setPlatform(value) {
        page.filterPlatform = value
        page.applyFilters()
    }

    function setViewMode(mode) {
        page.viewMode = mode
        bridge.setSetting("games_view", mode)
        Qt.callLater(page.requestVisible)
    }

    // Covers and identification are requested for what is on screen.
    function requestVisible() {
        if (gameModel.count === 0)
            return
        if (page.viewMode === "list") {
            var rowHeight = 72
            var firstRow = Math.max(0, Math.floor(gameList.contentY / rowHeight) - 1)
            var rows = Math.ceil(gameList.height / rowHeight) + 2
            bridge.requestRange(firstRow, Math.min(gameModel.count - 1, firstRow + rows))
            return
        }
        // The wall is a Flow: every card exists, so ask for the whole library.
        bridge.requestRange(0, gameModel.count - 1)
    }

    function openDetail(key, name, path, platformLabel, direct3d, arch, statusText, statusKind, coverUrl, platform) {
        gameSheet.gameKey = key
        gameSheet.gameName = name
        gameSheet.installPath = path
        gameSheet.platformLabel = platformLabel
        gameSheet.platform = platform
        gameSheet.direct3d = direct3d
        gameSheet.arch = arch
        gameSheet.statusText = statusText
        gameSheet.statusKind = statusKind
        gameSheet.coverUrl = coverUrl
        gameSheet.open()
    }

    onViewModeChanged: Qt.callLater(page.requestVisible)

    Connections {
        target: bridge
        function onGamesReady(count) {
            page.platformOptions = bridge.platformOptions()
            page.dxtkCounts = bridge.dxtkCounts()
            Qt.callLater(page.requestVisible)
        }
        function onStatusesReady(items) {
            page.dxtkCounts = bridge.dxtkCounts()
        }
        function onLanguageChanged() {
            // The translator was swapped at runtime (§28): re-pull the derived
            // strings so the platform filter chips and DXVK-state counts show
            // in the new language.
            page.platformOptions = bridge.platformOptions()
            page.dxtkCounts = bridge.dxtkCounts()
        }
        function onDetected(key, direct3d, arch) {
            // Keep an open dialog in step with a detection that just finished.
            if (gameSheet.visible && key === gameSheet.gameKey) {
                gameSheet.direct3d = direct3d
                gameSheet.arch = arch
            }
        }
    }

    // A slim scroll bar with no full-height track.
    component SlimBar: ScrollBar {
        policy: ScrollBar.AsNeeded
        width: 8
        background: Item {}
        contentItem: Rectangle {
            implicitWidth: 6
            radius: Th.radiusMicro
            color: Th.borderStrong
            opacity: parent.pressed ? 1.0 : 0.6
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }
    }

    // Toolbar buttons (text button and icon button) share one look.
    // §27: one clickable column heading. Bold with an ↑/↓ arrow while its key
    // is the active sort; the click goes to bridge.setSort, and the model
    // itself flips direction when the same column is clicked again.
    component SortHead: Item {
        id: head
        property string label: ""
        property string key: ""
        property bool alignLeft: false
        height: 32

        Rectangle {
            anchors.fill: parent
            radius: Th.radiusControl - 2
            color: headMouse.containsMouse ? Th.surfaceHover : "transparent"
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            x: head.alignLeft ? 0 : (head.width - width) / 2
            text: head.label + (gameModel.sortKey === head.key
                                ? (gameModel.sortDescending ? " ↓" : " ↑") : "")
            color: gameModel.sortKey === head.key ? Th.text : Th.textMuted
            font.pixelSize: Th.fontCaption
            font.bold: gameModel.sortKey === head.key
        }
        MouseArea {
            id: headMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: bridge.setSort(head.key)
        }
    }

    component BarButton: Button {
        id: bar
        property bool primary: false
        padding: 6
        background: Rectangle {
            radius: Th.radiusControl
            color: bar.primary
                 ? (bar.hovered ? Th.primaryHover : Th.primary)
                 : (bar.hovered ? Th.surfaceHover : Th.surfaceAlt)
        }
        contentItem: Text {
            text: bar.text
            color: bar.primary ? Th.primaryText : Th.text
            font.pixelSize: Th.fontSmall
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- toolbar -----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            color: Th.surface

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Th.pad
                anchors.rightMargin: Th.pad
                spacing: Th.space3

                TextField {
                    id: search
                    Layout.preferredWidth: 220
                    Layout.alignment: Qt.AlignVCenter
                    placeholderText: qsTr("搜索游戏…")
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
                    onTextChanged: page.applyFilters()
                }

                BarButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: "▽ " + page.filterSummary()
                    onClicked: filterSheet.open()
                }

                Item { Layout.fillWidth: true }

                BarButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("＋ 添加文件夹")
                    onClicked: bridge.addManualGame()
                }

                BarButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("扫描")
                    primary: true
                    onClicked: bridge.scanGames()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Th.borderSubtle
        }

        // --- views -------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Card wall: a Flow, because section headings must span the row and
            // uniform grid cells cannot do that.
            Flickable {
                id: wall
                objectName: "gameGrid"
                anchors.fill: parent
                visible: page.viewMode === "grid"
                clip: true
                contentWidth: width
                contentHeight: flow.height + Th.pad * 2
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: SlimBar {}

                onContentYChanged: page.requestVisible()
                onHeightChanged: page.requestVisible()
                onWidthChanged: page.requestVisible()

                WheelHandler {
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: function (wheel) {
                        var step = (Th.cardHeight + Th.cardFooter + Th.gap) * 0.9
                        var delta = wheel.pixelDelta.y !== 0
                                  ? wheel.pixelDelta.y * 2
                                  : (wheel.angleDelta.y / 120) * step
                        var limit = Math.max(0, wall.contentHeight - wall.height)
                        wall.contentY = Math.max(0, Math.min(limit, wall.contentY - delta))
                        wheel.accepted = true
                    }
                }

                Flow {
                    id: flow
                    objectName: "gameWall"
                    x: Th.pad
                    y: Th.pad
                    width: wall.width - Th.pad * 2
                    spacing: Th.gap

                    // 自适应卡墙：Flow 只换行不拉伸，定宽卡片的行尾会留下
                    // 参差空白（真机截图反馈）。列数由最小卡宽推出，单元格
                    // 宽度精确等分行宽——每个整行都与左右边距对齐，列数随
                    // 窗口宽度增减。0.02px 收缩防浮点累计误差导致提前换行。
                    readonly property int cols: Math.max(1, Math.floor((width + Th.gap) / (Th.cardWidth + Th.gap)))
                    readonly property real cellW: (width - (cols - 1) * Th.gap) / cols - 0.02

                    Repeater {
                        model: gameModel

                        delegate: Item {
                            readonly property bool isHeader: model.gameKind === "header"
                            width: isHeader ? flow.width : flow.cellW
                            height: isHeader ? 44 : Th.cardHeight + Th.cardFooter

                            Text {
                                visible: parent.isHeader
                                anchors.left: parent.left
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: Th.space2
                                text: parent.isHeader ? model.name : ""
                                color: Th.text
                                font.pixelSize: Th.fontTitle
                                font.bold: true
                            }

                            Rectangle {
                                visible: parent.isHeader
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Th.borderSubtle
                            }

                            GameCard {
                                visible: !parent.isHeader
                                gameKey: model.gameKey
                                title: model.name
                                platform: model.platform
                                platformLabel: model.platformLabel
                                subtitle: (model.direct3d === "" ? qsTr("识别中…")
                                           : (model.direct3d === "Unknown" ? qsTr("Direct3D 未知") : model.direct3d))
                                statusText: model.statusText
                                statusKind: model.statusKind
                                coverUrl: model.coverUrl
                                coverCardUrl: model.coverCardUrl

                                onActivated: page.openDetail(model.gameKey, model.name, model.installPath,
                                                             model.platformLabel, model.direct3d,
                                                             model.arch, model.statusText, model.statusKind,
                                                             model.coverUrl, model.platform)
                                onOpened: page.openDetail(model.gameKey, model.name, model.installPath,
                                                          model.platformLabel, model.direct3d, model.arch,
                                                          model.statusText, model.statusKind, model.coverUrl,
                                                          model.platform)
                            }
                        }
                    }
                }
            }

            // List: one rounded row per game, headings included.
            ListView {
                id: gameList
                objectName: "gameList"
                anchors.fill: parent
                visible: page.viewMode === "list"
                clip: true
                model: gameModel
                spacing: Th.space1
                topMargin: 33 + Th.pad
                bottomMargin: Th.pad
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: SlimBar {}

                // §27: Explorer-style column headings, pinned above the list.
                // Column edges mirror the row layout below: 名称 starts where
                // the row's name text starts, the three metadata headings
                // share the metadata strip, and DXVK lines up with the status
                // chip via the invisible placeholders (same fixed 96px chip
                // and same buttons, so the edge is exact without touching the
                // row delegates). OverlayHeader keeps it fixed while the list
                // scrolls; the solid background covers rows passing under it.
                headerPositioning: ListView.OverlayHeader
                header: Rectangle {
                    // OverlayHeader pins the item but does NOT size it, so the
                    // width must follow the view explicitly.
                    width: gameList.width
                    color: Th.surface
                    height: 33

                    readonly property real nameLeft: Th.pad + Th.space3 + 36 + Th.space3
                    readonly property real nameWidth: Math.min((gameList.width - 2 * Th.pad) * 0.42, 480)
                    readonly property real metaLeft: nameLeft + nameWidth + Th.space3
                    readonly property real metaRight: chipPH.x - Th.space3

                    BarButton {
                        id: folderPH
                        visible: false
                        text: "打开目录"
                        anchors.right: parent.right
                        anchors.rightMargin: Th.space3
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    BarButton {
                        id: detailPH
                        visible: false
                        text: "详情"
                        anchors.right: folderPH.left
                        anchors.rightMargin: Th.space2
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    StatusChip {
                        id: chipPH
                        visible: false
                        fixedWidth: true
                        text: "已装 DXVK"
                        anchors.right: detailPH.left
                        anchors.rightMargin: Th.space2
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    SortHead {
                        x: parent.nameLeft
                        width: parent.nameWidth
                        alignLeft: true
                        label: qsTr("名称")
                        key: "name"
                    }
                    SortHead {
                        x: parent.metaLeft
                        width: (parent.metaRight - parent.metaLeft) / 3
                        label: qsTr("平台")
                        key: "platform"
                    }
                    SortHead {
                        x: parent.metaLeft + (parent.metaRight - parent.metaLeft) / 3
                        width: (parent.metaRight - parent.metaLeft) / 3
                        label: "Direct3D"
                        key: "direct3d"
                    }
                    SortHead {
                        x: parent.metaLeft + (parent.metaRight - parent.metaLeft) * 2 / 3
                        width: (parent.metaRight - parent.metaLeft) / 3
                        label: qsTr("架构")
                        key: "arch"
                    }
                    SortHead {
                        x: chipPH.x
                        width: 96
                        label: "DXVK"
                        key: "dxtk"
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1
                        color: Th.borderSubtle
                    }
                }

                onContentYChanged: page.requestVisible()
                onHeightChanged: page.requestVisible()

                add: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1
                                      duration: 160; easing.type: Easing.OutCubic }
                }

                WheelHandler {
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: function (wheel) {
                        var step = 64 * 2
                        var delta = wheel.pixelDelta.y !== 0
                                  ? wheel.pixelDelta.y * 2
                                  : (wheel.angleDelta.y / 120) * step
                        var limit = Math.max(0, gameList.contentHeight - gameList.height)
                        gameList.contentY = Math.max(0, Math.min(limit, gameList.contentY - delta))
                        wheel.accepted = true
                    }
                }

                delegate: Item {
                    id: row
                    required property string gameKind
                    required property string gameKey
                    required property string name
                    required property string platformLabel
                    required property string direct3d
                    required property string arch
                    required property string statusText
                    required property string statusKind
                    required property string coverUrl
                    required property string installPath

                    readonly property bool isHeader: row.gameKind === "header"
                    width: gameList.width
                    height: row.isHeader ? 40 : 64

                    // --- section heading ---------------------------------
                    Text {
                        visible: row.isHeader
                        anchors.left: parent.left
                        anchors.leftMargin: Th.pad
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: Th.space2
                        text: row.isHeader ? row.name : ""
                        color: Th.text
                        font.pixelSize: Th.fontTitle
                        font.bold: true
                    }

                    Rectangle {
                        visible: row.isHeader
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: Th.pad
                        anchors.rightMargin: Th.pad
                        anchors.bottom: parent.bottom
                        height: 1
                        color: Th.borderSubtle
                    }

                    // --- one game ----------------------------------------
                    Rectangle {
                        id: card
                        visible: !row.isHeader
                        anchors.fill: parent
                        anchors.leftMargin: Th.pad
                        anchors.rightMargin: Th.pad
                        radius: Th.radiusCard
                        color: rowHover.containsMouse ? Th.surfaceHover : Th.surface

                        Behavior on color { ColorAnimation { duration: 120 } }

                        MouseArea {
                            id: rowHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: page.openDetail(row.gameKey, row.name, row.installPath,
                                                       row.platformLabel, row.direct3d, row.arch,
                                                       row.statusText, row.statusKind, row.coverUrl,
                                                       row.platform)
                        }

                        // Circular cover thumbnail.
                        Rectangle {
                            id: avatar
                            width: 36
                            height: 36
                            radius: 18
                            anchors.left: parent.left
                            anchors.leftMargin: Th.space3
                            anchors.verticalCenter: parent.verticalCenter
                            color: Th.platformColor((row.platform || "").toLowerCase())
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: row.coverRoundUrl
                                asynchronous: true
                                fillMode: Image.PreserveAspectCrop
                                visible: status === Image.Ready
                            }
                            Text {
                                anchors.centerIn: parent
                                text: (row.name || "?").substring(0, 1).toUpperCase()
                                color: "#ffffff"
                                font.pixelSize: Th.fontSubtitle
                                font.bold: true
                                visible: row.coverRoundUrl === ""
                            }
                        }

                        // Name column: capped at 42% of row width so the
                        // metadata column gets a fixed starting point and the
                        // 1400px void disappears (§24 scheme A).
                        Text {
                            id: nameText
                            anchors.left: avatar.right
                            anchors.leftMargin: Th.space3
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(parent.width * 0.42, 480)
                            text: row.isHeader ? "" : row.name
                            color: Th.text
                            font.pixelSize: Th.fontBody
                            elide: Text.ElideRight
                        }

                        // Metadata column: platform · Direct3D · arch on one
                        // line, starting right after the name and filling up
                        // to the status chip.
                        Text {
                            id: metaText
                            anchors.left: nameText.right
                            anchors.leftMargin: Th.space3
                            anchors.right: statusChip.left
                            anchors.rightMargin: Th.space3
                            anchors.verticalCenter: parent.verticalCenter
                            text: row.platformLabel + " · " +
                                  (row.direct3d === "" ? qsTr("识别中…")
                                   : (row.direct3d === "Unknown" ? qsTr("Direct3D 未知") : row.direct3d)) +
                                  (row.arch !== "" ? " · " + row.arch : "")
                            color: Th.textMuted
                            font.pixelSize: Th.fontCaption
                            elide: Text.ElideRight
                        }

                        StatusChip {
                            id: statusChip
                            fixedWidth: true
                            text: row.statusText
                            kind: row.statusKind
                            anchors.right: detailButton.left
                            anchors.rightMargin: Th.space2
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        BarButton {
                            id: detailButton
                            text: qsTr("详情")
                            anchors.right: folderButton.left
                            anchors.rightMargin: Th.space2
                            anchors.verticalCenter: parent.verticalCenter
                            onClicked: page.openDetail(row.gameKey, row.name, row.installPath,
                                                       row.platformLabel, row.direct3d, row.arch,
                                                       row.statusText, row.statusKind, row.coverUrl,
                                                       row.platform)
                        }

                        BarButton {
                            id: folderButton
                            text: qsTr("打开目录")
                            anchors.right: parent.right
                            anchors.rightMargin: Th.space3
                            anchors.verticalCenter: parent.verticalCenter
                            onClicked: bridge.openFolder(row.installPath)
                        }
                    }
                }
            }

            // Empty state floats above the views.
            Column {
                anchors.centerIn: parent
                width: Math.min(parent.width - 80, 620)
                spacing: 12
                visible: gameModel.count === 0

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("还没有游戏")
                    color: Th.text
                    font.pixelSize: Th.fontTitle
                    font.bold: true
                }
                Text {
                    width: parent.width
                    text: qsTr("点「扫描」读取 Steam 库（含所有库文件夹），或「＋ 添加文件夹」指定任意游戏目录。")
                    color: Th.textMuted
                    font.pixelSize: Th.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }
                BarButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("开始扫描")
                    primary: true
                    onClicked: bridge.scanGames()
                }
            }
        }
    }

    FilterSheet {
        id: filterSheet
        dxtkFilter: page.dxtkFilter
        platformFilter: page.filterPlatform
        platformOptions: page.platformOptions
        dxtkCounts: page.dxtkCounts
        viewMode: page.viewMode
        sortKey: gameModel.sortKey
        sortDescending: gameModel.sortDescending

        onDxtkChosen: (value) => page.setDxtkFilter(value)
        onPlatformChosen: (value) => page.setPlatform(value)
        onViewChosen: (mode) => page.setViewMode(mode)
        onSortChosen: (key) => bridge.setSort(key)
        onOrderChosen: (descending) => bridge.setSortDescending(descending)
    }

    GameDetailDialog {
        id: gameSheet
    }
}
