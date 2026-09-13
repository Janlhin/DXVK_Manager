import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

Item {
    id: page

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

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- top bar -----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            color: Th.surface

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Th.pad
                anchors.rightMargin: Th.pad
                spacing: 8

                TextField {
                    id: search
                    Layout.preferredWidth: 200
                    placeholderText: "搜索游戏…"
                    color: Th.text
                    placeholderTextColor: Th.textDim
                    background: Rectangle {
                        radius: Th.radiusSmall
                        color: Th.surfaceAlt
                        border.color: search.activeFocus ? Th.accent : Th.border
                        Behavior on border.color { ColorAnimation { duration: 120 } }
                    }
                    onTextChanged: bridge.setFilter(text, page.filterPlatform, page.dxtkFilter)
                }

                Repeater {
                    model: page.platformOptions
                    delegate: Button {
                        text: modelData.label + " " + modelData.count
                        checkable: true
                        checked: page.filterPlatform === modelData.value
                        onClicked: {
                            page.filterPlatform = modelData.value
                            bridge.setFilter(search.text, page.filterPlatform, page.dxtkFilter)
                        }
                        background: Rectangle {
                            radius: Th.radiusSmall
                            color: parent.checked ? Th.accentDark
                                 : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? "#ffffff" : Th.textMuted
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // --- DXVK state filter ------------------------------------
                Row {
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 4

                    Repeater {
                        model: [
                            { value: "all", label: "全部" },
                            { value: "patched", label: "已装 DXVK" },
                            { value: "clean", label: "未装" }
                        ]
                        delegate: Button {
                            text: modelData.label + " " + page.dxtkCount(modelData.value)
                            checkable: true
                            checked: page.dxtkFilter === modelData.value
                            onClicked: page.setDxtkFilter(modelData.value)
                            background: Rectangle {
                                radius: Th.radiusSmall
                                color: parent.checked ? Th.accentDark
                                     : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : Th.textMuted
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // --- view switch ------------------------------------------
                Row {
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 4

                    Button {
                        text: "卡片"
                        checkable: true
                        checked: page.viewMode === "grid"
                        onClicked: page.setViewMode("grid")
                        background: Rectangle {
                            radius: Th.radiusSmall
                            color: parent.checked ? Th.accentDark
                                 : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? "#ffffff" : Th.textMuted
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "列表"
                        checkable: true
                        checked: page.viewMode === "list"
                        onClicked: page.setViewMode("list")
                        background: Rectangle {
                            radius: Th.radiusSmall
                            color: parent.checked ? Th.accentDark
                                 : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? "#ffffff" : Th.textMuted
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                Button {
                    text: "添加文件夹…"
                    onClicked: bridge.addManualGame()
                    background: Rectangle { radius: Th.radiusSmall
                                            color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                            Behavior on color { ColorAnimation { duration: 120 } } }
                    contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: 12
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
                }

                Button {
                    text: "扫描"
                    padding: 8
                    onClicked: { bridge.scanGames(); page.selectedKey = "" }
                    background: Rectangle { radius: Th.radiusSmall
                                            color: parent.hovered ? Th.primaryHover : Th.primary
                                            Behavior on color { ColorAnimation { duration: 120 } } }
                    contentItem: Text { text: parent.text; color: Th.primaryText; font.bold: true
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
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

            // Qt's default wheel step (60 px) crawls on a wall of cards; this
            // scrolls by rows instead, and still honours touchpad pixel deltas.
            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function (event) {
                    var step = grid.cellHeight * 1.8
                    var delta = event.pixelDelta.y !== 0
                              ? event.pixelDelta.y * 2
                              : (event.angleDelta.y / 120) * step
                    var limit = Math.max(0, grid.contentHeight - VIEW.height)
                    VIEW.contentY = Math.max(0, Math.min(limit, VIEW.contentY - delta))
                    event.accepted = true
                }
            }

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
                    subtitle: (model.direct3d && model.direct3d !== "Unknown" && model.direct3d !== ""
                               ? model.direct3d : "") +
                              (model.arch ? (model.direct3d && model.direct3d !== "Unknown" &&
                                             model.direct3d !== "" ? " · " : "") + model.arch : "")

                    onActivated: page.selectGame(model.gameKey, model.name, model.installPath,
                                                 model.platformLabel, model.direct3d,
                                                 model.arch, model.statusText, model.statusKind)
                }
                }
            }

            // --- list view ------------------------------------------------
            ListView {
                id: gameList
                objectName: "gameList"
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
                    var limit = Math.max(0, gameList.contentHeight - VIEW.height)
                    VIEW.contentY = Math.max(0, Math.min(limit, VIEW.contentY - delta))
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
                            font.pixelSize: 14
                            font.bold: true
                            visible: gameRow.coverUrl === ""
                        }
                    }

                    Row {
                        anchors.left: thumb.right
                        anchors.leftMargin: 12
                        anchors.right: parent.right
                        anchors.rightMargin: Th.pad
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12

                        Text {
                            width: Math.max(160, gameRow.width - 560)
                            text: gameRow.name
                            color: Th.text
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            width: 90
                            text: gameRow.platformLabel
                            color: Th.textMuted
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            width: 110
                            text: gameRow.direct3d === ""
                                  ? "识别中…"
                                  : (gameRow.direct3d === "Unknown" ? "未知" : gameRow.direct3d)
                            color: Th.textMuted
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            width: 60
                            text: gameRow.arch !== "" ? gameRow.arch : "—"
                            color: Th.textMuted
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            radius: Th.radiusMicro
                            color: Th.statusBg(gameRow.statusKind)
                            width: rowStatus.implicitWidth + 12
                            height: rowStatus.implicitHeight + 6

                            Text {
                                id: rowStatus
                                anchors.centerIn: parent
                                text: gameRow.statusText
                                color: Th.statusColor(gameRow.statusKind)
                                font.pixelSize: 11
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
                    font.pixelSize: 18
                    font.bold: true
                }
                Text {
                    width: parent.width
                    text: "点「扫描」读取 Steam 库（含所有库文件夹），或「添加文件夹…」指定任意游戏目录。"
                    color: Th.textMuted
                    font.pixelSize: 12
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
                                        font.pixelSize: 13
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
                }
            }
        }

        // --- details -----------------------------------------------------
        Rectangle {
            id: detail
            objectName: "gameDetails"
            Layout.fillWidth: true
            Layout.preferredHeight: detail.gameKey !== "" ? 100 : 0
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
                anchors.fill: parent
                anchors.margins: 12
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: detail.name
                        color: Th.text
                        font.pixelSize: 15
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.maximumWidth: 420
                    }
                    Rectangle {
                        radius: Th.radiusMicro
                        color: Th.statusBg(detail.statusKind)
                        width: statusLabel.implicitWidth + 12
                        height: statusLabel.implicitHeight + 5
                        Text {
                            id: statusLabel
                            anchors.centerIn: parent
                            text: detail.statusText
                            color: Th.statusColor(detail.statusKind)
                            font.pixelSize: 11
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "打开目录"
                        onClicked: bridge.openFolder(detail.path)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                                Behavior on color { ColorAnimation { duration: 120 } } }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                    Button {
                        text: "移除 DXVK"
                        onClicked: bridge.removeDxvk(detail.gameKey)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                                Behavior on color { ColorAnimation { duration: 120 } } }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                    Button {
                        text: "还原原始 DLL"
                        onClicked: bridge.restoreGame(detail.gameKey)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                                                Behavior on color { ColorAnimation { duration: 120 } } }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: "路径：" + detail.path
                    color: Th.textMuted
                    font.pixelSize: 11
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    text: "平台：" + detail.platform +
                          "    Direct3D：" + (detail.direct3d === "" ? "识别中…"
                                            : (detail.direct3d === "Unknown" ? "未知" : detail.direct3d)) +
                          "    架构：" + (detail.arch ? detail.arch : "识别中…")
                    color: Th.textMuted
                    font.pixelSize: 11
                }
            }
        }
    }
}