import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

Item {
    id: page
    objectName: "gamesPage"

    Shortcut {
        sequence: "Esc"
        onActivated: page.clearSelection()
    }

    onVisibleChanged: if (!visible) page.clearSelection()

    property string selectedKey: ""
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

    // The details bar used to stay until another game was picked. It now
    // closes on a click in empty space, a right click, Esc, or leaving the page.
    function clearSelection() {
        if (page.selectedKey === "" && detail.gameKey === "")
            return
        page.selectedKey = ""
        detail.gameKey = ""
        detail.name = ""
    }

    function setDxtkFilter(value) {
        page.dxtkFilter = value
        bridge.setSetting("games_dxtk_filter", value)
        bridge.setFilter(search.text, page.filterPlatform, value)
        Qt.callLater(page.requestVisible)
    }

    // A slim scroll bar with no full-height track (the default style draws a
    // dark column next to the content, which looks like a broken panel).
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

    // Ask the bridge for what is on screen: covers plus Direct3D/architecture
    // identification for exactly those games.
    function requestVisible() {
        if (gameModel.count === 0)
            return
        if (page.viewMode === "list") {
            var rowHeight = 46
            var firstRow = Math.max(0, Math.floor(gameList.contentY / rowHeight) - 1)
            var rows = Math.ceil(gameList.height / rowHeight) + 2
            bridge.requestRange(firstRow, Math.min(gameModel.count - 1, firstRow + rows))
            return
        }
        var columns = page.gridColumns(grid.width)
        var cardRow = Th.cardHeight + Th.cardFooter + Th.gap
        var first = Math.max(0, Math.floor((grid.contentY - grid.topMargin) / cardRow)) * columns
        var lastRow = Math.floor((grid.contentY - grid.topMargin + grid.height) / cardRow) + 1
        var last = Math.min(gameModel.count - 1, (lastRow + 1) * columns - 1)
        bridge.requestRange(first, last)
    }

    // Double clicking a card opens the per-game sheet: the only place where a
    // DXVK build can be applied to that game.
    function openDetail(key, name, path, platformLabel, direct3d, arch,
                        statusText, statusKind, coverUrl) {
        page.selectGame(key, name, path, platformLabel, direct3d, arch, statusText, statusKind)
        gameSheet.gameKey = key
        gameSheet.gameName = name
        gameSheet.installPath = path
        gameSheet.platformLabel = platformLabel
        gameSheet.direct3d = direct3d
        gameSheet.arch = arch
        gameSheet.statusText = statusText
        gameSheet.statusKind = statusKind
        gameSheet.coverUrl = coverUrl
        gameSheet.open()
    }

    function selectGame(key, name, path, platformLabel, direct3d, arch, statusText, statusKind) {
        page.selectedKey = key
        detail.gameKey = key
        detail.name = name
        detail.path = path
        detail.platform = platformLabel
        detail.direct3d = direct3d
        detail.arch = arch
        detail.statusText = statusText
        detail.statusKind = statusKind
        bridge.detectGame(key)
    }

    // How many cards fit, and how wide each cell must be so that the columns
    // share the leftover width evenly (no dead strip at the right edge).
    function gridColumns(available) {
        var usable = Math.max(0, available - Th.pad * 2)
        return Math.max(1, Math.floor((usable + Th.gap) / (Th.cardWidth + Th.gap)))
    }

    function gridCellWidth(available) {
        var usable = Math.max(0, available - Th.pad * 2)
        return usable / gridColumns(available)
    }

    function setViewMode(mode) {
        page.viewMode = mode
        bridge.setSetting("games_view", mode)
        Qt.callLater(page.requestVisible)
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
        function onDetected(key, direct3d, arch) {
            if (key === page.selectedKey) {
                detail.direct3d = direct3d
                detail.arch = arch
            }
        }
    }

    GameDetailDialog {
        id: gameSheet
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- top bar -----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            color: Th.surface

            // Sits behind the controls: a click that misses every button counts
            // as "clicked somewhere else" and closes the details bar.
            MouseArea {
                anchors.fill: parent
                onClicked: page.clearSelection()
            }

            // Two groups of mutually exclusive buttons used to sit side by side
            // with the same 4 px gap, so five buttons read as one control.
            // Each group now lives in its own track, and the tracks are spaced.
            component Track: Rectangle {
                id: track
                default property alias content: trackRow.data
                implicitWidth: trackRow.implicitWidth + Th.space1
                implicitHeight: trackRow.implicitHeight + Th.space1
                radius: Th.radiusControl
                color: Th.surfaceAlt
                border.width: 1
                border.color: Th.borderSubtle

                Row {
                    id: trackRow
                    anchors.centerIn: parent
                    spacing: 2
                }
            }

            component Segment: Button {
                padding: 6
                checkable: true
                background: Rectangle {
                    radius: Th.radiusControl - 2
                    color: parent.checked ? Th.accentDark
                         : (parent.hovered ? Th.surfaceHover : "transparent")
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

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Th.pad
                anchors.rightMargin: Th.pad
                spacing: Th.space3

                TextField {
                    id: search
                    Layout.preferredWidth: 200
                    Layout.alignment: Qt.AlignVCenter
                    placeholderText: "搜索游戏…"
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
                    onTextChanged: bridge.setFilter(text, page.filterPlatform, page.dxtkFilter)
                }

                // --- platform --------------------------------------------------
                Track {
                    Layout.alignment: Qt.AlignVCenter
                    Repeater {
                        model: page.platformOptions
                        delegate: Segment {
                            text: modelData.label + " " + modelData.count
                            checked: page.filterPlatform === modelData.value
                            onClicked: {
                                page.filterPlatform = modelData.value
                                bridge.setFilter(search.text, page.filterPlatform, page.dxtkFilter)
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // --- DXVK state ------------------------------------------------
                Track {
                    Layout.alignment: Qt.AlignVCenter
                    Repeater {
                        model: [
                            { value: "all", label: "全部" },
                            { value: "patched", label: "已装 DXVK" },
                            { value: "clean", label: "未装" }
                        ]
                        delegate: Segment {
                            text: modelData.label + " " + page.dxtkCount(modelData.value)
                            checked: page.dxtkFilter === modelData.value
                            onClicked: page.setDxtkFilter(modelData.value)
                        }
                    }
                }

                // --- view mode ------------------------------------------------
                Track {
                    Layout.alignment: Qt.AlignVCenter
                    Segment {
                        text: "卡片"
                        checked: page.viewMode === "grid"
                        onClicked: page.setViewMode("grid")
                    }
                    Segment {
                        text: "列表"
                        checked: page.viewMode === "list"
                        onClicked: page.setViewMode("list")
                    }
                }

                Button {
                    Layout.alignment: Qt.AlignVCenter
                    text: "添加文件夹…"
                    padding: 6
                    onClicked: bridge.addManualGame()
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

                Button {
                    Layout.alignment: Qt.AlignVCenter
                    text: "扫描"
                    padding: 6
                    onClicked: { bridge.scanGames(); page.selectedKey = "" }
                    background: Rectangle {
                        radius: Th.radiusControl
                        color: parent.hovered ? Th.primaryHover : Th.primary
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Text {
                        text: parent.text
                        color: Th.primaryText
                        font.pixelSize: Th.fontSmall
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        // --- views -------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            GridView {
                id: grid
                objectName: "gameGrid"
                anchors.fill: parent
                visible: page.viewMode === "grid"
                clip: true
                cellWidth: page.gridCellWidth(width)
                cellHeight: Th.cardHeight + Th.cardFooter + Th.gap
                topMargin: Th.pad
                bottomMargin: Th.pad
                leftMargin: Th.pad
                rightMargin: Th.pad
                cacheBuffer: 800
                boundsBehavior: Flickable.StopAtBounds
                model: gameModel
                ScrollBar.vertical: SlimBar {}

                add: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1
                                      duration: 200; easing.type: Easing.OutCubic }
                }
                onContentYChanged: page.requestVisible()
                onHeightChanged: page.requestVisible()
                onWidthChanged: page.requestVisible()

                // A click that lands on no card closes the details bar.
                TapHandler {
                    onTapped: function (event) {
                        var hit = grid.itemAt(event.position.x + grid.contentX,
                                              event.position.y + grid.contentY)
                        if (hit === null)
                            page.clearSelection()
                    }
                }

                // Wheel scrolling, by rows: Qt's default 60 px per notch
                // crawls on a wall of 330 px cells.
                WheelHandler {
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: function (wheel) {
                        var step = grid.cellHeight * 1.5
                        var delta = wheel.pixelDelta.y !== 0
                                  ? wheel.pixelDelta.y * 2
                                  : (wheel.angleDelta.y / 120) * step
                        var limit = Math.max(0, grid.contentHeight - grid.height)
                        grid.contentY = Math.max(0, Math.min(limit, grid.contentY - delta))
                        wheel.accepted = true
                    }
                }


            // Qt's default wheel step (60 px) crawls on a wall of cards; this
            // scrolls by rows instead, and still honours touchpad pixel deltas.
                // Values come from the model object explicitly: declaring
                // "required property coverUrl" here collided with the property
                // GameCard already declares, so the model value was dropped and
                // covers never appeared on the cards.
                // The card keeps its own size and is centred inside the cell.
                delegate: Item {
                    width: grid.cellWidth
                    height: grid.cellHeight

                GameCard {
                    anchors.horizontalCenter: parent.horizontalCenter
                    gameKey: model.gameKey
                    title: model.name
                    platform: model.platform
                    platformLabel: model.platformLabel
                    statusText: model.statusText
                    statusKind: model.statusKind
                    coverUrl: model.coverUrl
                    selected: page.selectedKey === model.gameKey
                    // The card is only 168 px wide, so it shows the Direct3D
                    // family; the architecture lives in the details panel.
                    subtitle: (model.direct3d === "" ? "识别中…"
                               : (model.direct3d === "Unknown" ? "Direct3D 未知" : model.direct3d))

                    onActivated: page.selectGame(model.gameKey, model.name, model.installPath,
                                                 model.platformLabel, model.direct3d,
                                                 model.arch, model.statusText, model.statusKind)
                    onOpened: page.openDetail(model.gameKey, model.name, model.installPath,
                                              model.platformLabel, model.direct3d, model.arch,
                                              model.statusText, model.statusKind, model.coverUrl)
                }
                }
            }

            // --- list view ------------------------------------------------
            ListView {
                id: gameList
                objectName: "gameList"

                TapHandler {
                    onTapped: function (event) {
                        var hit = gameList.itemAt(event.position.x + gameList.contentX,
                                                  event.position.y + gameList.contentY)
                        if (hit === null)
                            page.clearSelection()
                    }
                }
                anchors.fill: parent
                visible: page.viewMode === "list"
                clip: true
                model: gameModel
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: SlimBar {}

                add: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1
                                      duration: 160; easing.type: Easing.OutCubic }
                }
                onContentYChanged: page.requestVisible()
                onHeightChanged: page.requestVisible()

            // Qt's default wheel step (60 px) crawls on a wall of cards; this
            // scrolls by rows instead, and still honours touchpad pixel deltas.
            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function (event) {
                    var step = 46 * 3
                    var delta = event.pixelDelta.y !== 0
                              ? event.pixelDelta.y * 2
                              : (event.angleDelta.y / 120) * step
                    var limit = Math.max(0, gameList.contentHeight - gameList.height)
                    gameList.contentY = Math.max(0, Math.min(limit, gameList.contentY - delta))
                    event.accepted = true
                }
            }

                delegate: Rectangle {
                    id: gameRow
                    required property int index
                    required property string gameKey
                    required property string name
                    required property string platform
                    required property string platformLabel
                    required property string statusText
                    required property string statusKind
                    required property string coverUrl
                    required property string direct3d
                    required property string arch
                    required property string installPath

                    width: gameList.width
                    height: 46
                    color: page.selectedKey === gameKey
                           ? Th.surfaceHover
                           : (index % 2 === 0 ? Th.bg : Th.surface)

                    Behavior on color { ColorAnimation { duration: 120 } }

                    // small cover thumbnail
                    Rectangle {
                        id: thumb
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: 28
                        height: 42
                        radius: Th.radiusMicro
                        color: Th.platformColor(gameRow.platform)
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: gameRow.coverUrl
                            asynchronous: true
                            fillMode: Image.PreserveAspectCrop
                            sourceSize.width: 56
                            sourceSize.height: 84
                            visible: status === Image.Ready
                        }

                        Text {
                            anchors.centerIn: parent
                            text: gameRow.name.substring(0, 1).toUpperCase()
                            color: "#ffffff"
                            font.pixelSize: Th.fontSubtitle
                            font.bold: true
                            visible: gameRow.coverUrl === ""
                        }
                    }

                    // Columns line up across rows and the name absorbs the
                    // slack; fixed widths left half the row empty on a wide
                    // window.
                    RowLayout {
                        anchors.left: thumb.right
                        anchors.leftMargin: Th.space3
                        anchors.right: parent.right
                        anchors.rightMargin: Th.pad
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Th.space4

                        Text {
                            Layout.fillWidth: true
                            text: gameRow.name
                            color: Th.text
                            font.pixelSize: Th.fontBody
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.preferredWidth: 80
                            text: gameRow.platformLabel
                            color: Th.textMuted
                            font.pixelSize: Th.fontBody
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.preferredWidth: 120
                            text: gameRow.direct3d === ""
                                  ? "识别中…"
                                  : (gameRow.direct3d === "Unknown" ? "未知" : gameRow.direct3d)
                            color: Th.textMuted
                            font.pixelSize: Th.fontBody
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.preferredWidth: 56
                            text: gameRow.arch !== "" ? gameRow.arch : "—"
                            color: Th.textMuted
                            font.pixelSize: Th.fontBody
                        }

                        Rectangle {
                            implicitWidth: rowStatus.implicitWidth + Th.space3
                            implicitHeight: rowStatus.implicitHeight + Th.space2
                            Layout.alignment: Qt.AlignVCenter
                            radius: Th.radiusMicro
                            color: Th.statusBg(gameRow.statusKind)
                            border.width: 1
                            border.color: Th.borderSubtle

                            Text {
                                id: rowStatus
                                x: (parent.width - width) / 2
                                y: (parent.height - height) / 2
                                text: gameRow.statusText
                                color: Th.statusColor(gameRow.statusKind)
                                font.pixelSize: Th.fontCaption
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: page.selectGame(gameRow.gameKey, gameRow.name, gameRow.installPath,
                                                   gameRow.platformLabel, gameRow.direct3d,
                                                   gameRow.arch, gameRow.statusText, gameRow.statusKind)
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
                    text: "还没有游戏"
                    color: Th.text
                    font.pixelSize: Th.fontTitle
                    font.bold: true
                }
                Text {
                    width: parent.width
                    text: "点「扫描」读取 Steam 库（含所有库文件夹），或「添加文件夹…」指定任意游戏目录。"
                    color: Th.textMuted
                    font.pixelSize: Th.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "开始扫描"
                    padding: 8
                    onClicked: bridge.scanGames()
                    background: Rectangle { radius: Th.radiusSmall
                                            color: parent.hovered ? Th.primaryHover : Th.primary }
                    contentItem: Text { text: parent.text; color: Th.primaryText; font.bold: true
                                        font.pixelSize: Th.fontBody
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
                }
            }

            // Right click anywhere in the list also closes the details bar.
            // The overlay accepts no button but the right one, so it never
            // interferes with clicking, hovering or scrolling the games.
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.RightButton
                onClicked: page.clearSelection()
            }
        }

        // --- details -----------------------------------------------------
        Rectangle {
            id: detail
            objectName: "gameDetails"
            Layout.fillWidth: true
            // Sized by its content: a fixed height left a blank line under
            // the last row of text.
            Layout.preferredHeight: detail.gameKey !== ""
                                   ? detailBody.implicitHeight + Th.space5
                                   : 0
            visible: detail.gameKey !== ""
            color: Th.surface

            property string gameKey: ""
            property string name: ""
            property string path: ""
            property string platform: ""
            property string direct3d: ""
            property string arch: ""
            property string statusText: ""
            property string statusKind: "muted"

            ColumnLayout {
                id: detailBody
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: Th.space3
                spacing: Th.space1

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Th.space3

                    Text {
                        text: detail.name
                        color: Th.text
                        font.pixelSize: Th.fontSubtitle
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.maximumWidth: 420
                    }
                    // A status chip: without a stroke and real padding the
                    // label read as part of the game title.
                    // Sized via implicitWidth/implicitHeight and positioned with
                    // x/y: centring the label with anchors while the parent's
                    // width depended on the label's implicit width was a binding
                    // loop, and Qt broke it - the chip collapsed to 12 px.
                    Rectangle {
                        implicitWidth: statusLabel.implicitWidth + Th.space3
                        implicitHeight: statusLabel.implicitHeight + Th.space2
                        radius: Th.radiusMicro
                        color: Th.statusBg(detail.statusKind)
                        border.width: 1
                        border.color: detail.statusKind === "ok" ? Th.ok
                                      : (detail.statusKind === "warn" ? Th.warn
                                         : (detail.statusKind === "error" ? Th.error : Th.border))
                        Text {
                            id: statusLabel
                            x: (parent.width - width) / 2
                            y: (parent.height - height) / 2
                            text: detail.statusText
                            color: Th.statusColor(detail.statusKind)
                            font.pixelSize: Th.fontCaption
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "打开目录"
                        onClicked: bridge.openFolder(detail.path)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                                Behavior on color { ColorAnimation { duration: 120 } } }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: Th.fontBody
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                    Button {
                        text: "移除 DXVK"
                        onClicked: bridge.removeDxvk(detail.gameKey)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                                Behavior on color { ColorAnimation { duration: 120 } } }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: Th.fontBody
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                    Button {
                        text: "还原原始 DLL"
                        onClicked: bridge.restoreGame(detail.gameKey)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                                Behavior on color { ColorAnimation { duration: 120 } } }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: Th.fontBody
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: "路径：" + detail.path
                    color: Th.textMuted
                    font.pixelSize: Th.fontCaption
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    text: "平台：" + detail.platform +
                          "    Direct3D：" + (detail.direct3d === "" ? "识别中…"
                                            : (detail.direct3d === "Unknown" ? "未知" : detail.direct3d)) +
                          "    架构：" + (detail.arch ? detail.arch : "识别中…")
                    color: Th.textMuted
                    font.pixelSize: Th.fontCaption
                }
            }
        }
    }
}