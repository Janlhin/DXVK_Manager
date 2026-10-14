import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// Version library: version cards on the left, the selected version's details on
// the right. The list loads itself - cache first, refreshed in the background -
// so switching between 官方 DXVK and DXVK-GPLAsync never leaves an empty screen
// waiting for a manual refresh.
Item {
    id: page
    objectName: "versionsPage"

    property string kind: "dxvk"
    property bool loading: false
    property var selected: null
    property var installedHere: []
    property var gameChoices: []
    property string chosenGame: ""

    readonly property real panelWidth: Math.max(320, Math.min(420, width * 0.28))

    function chooseKind(value) {
        if (page.kind === value)
            return
        page.kind = value
        page.selected = null
        bridge.loadLocalVersions()
        bridge.loadVersions(value, false)
    }

    function reload(force) {
        page.loading = true
        bridge.loadVersions(page.kind, force)
    }

    Component.onCompleted: {
        page.gameChoices = bridge.gameOptions()
        bridge.loadLocalVersions()
        bridge.loadVersions(page.kind, false)
    }

    // Returning to the page shows the cache at once; the bridge refreshes a
    // stale cache in the background.
    onVisibleChanged: if (visible) bridge.loadVersions(page.kind, false)

    Connections {
        target: bridge

        function onVersionsReady(payload) {
            if (payload.kind !== page.kind)
                return
            page.loading = false
            page.installedHere = payload.installed || []
            releaseModel.clear()
            var releases = payload.releases || []
            for (var i = 0; i < releases.length; i++) {
                var r = releases[i]
                releaseModel.append({
                    version: r.version,
                    date: r.date,
                    size: r.size,
                    notes: r.notes || "",
                    summary: r.summary || "",
                    kindLabel: r.kindLabel || "",
                    installed: page.installedHere.indexOf(
                        page.kind === "gplasync" ? r.version.replace(/^v/, "") : r.version) !== -1
                })
            }
        }

        function onLocalVersionsReady(payload) {
            page.installedHere = payload[page.kind] || []
            for (var i = 0; i < releaseModel.count; i++) {
                var row = releaseModel.get(i)
                var name = page.kind === "gplasync" ? row.version.replace(/^v/, "") : row.version
                releaseModel.setProperty(i, "installed", page.installedHere.indexOf(name) !== -1)
            }
            // Keep the open detail panel in step with a delete/download that
            // just finished, so the 删除 button enables/disables correctly.
            if (page.selected !== null)
                page.selected.installed = page.installedHere.indexOf(
                    page.kind === "gplasync" ? page.selected.version.replace(/^v/, "") : page.selected.version) !== -1
        }

        function onProgressChanged(fraction, label) {
            progress.visible = fraction >= 0
            progress.value = fraction >= 0 ? fraction : 0
            progress.label = label
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

                Track {
                    Layout.alignment: Qt.AlignVCenter
                    Segment {
                        text: qsTr("官方 DXVK")
                        checked: page.kind === "dxvk"
                        onClicked: page.chooseKind("dxvk")
                    }
                    Segment {
                        text: "DXVK-GPLAsync"
                        checked: page.kind === "gplasync"
                        onClicked: page.chooseKind("gplasync")
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    text: page.installedHere.length > 0
                          ? qsTr("已下载 %1 个").arg(page.installedHere.length)
                          : qsTr("还没有下载版本")
                    color: page.installedHere.length > 0 ? Th.ok : Th.textMuted
                    font.pixelSize: Th.fontCaption
                }

                BarButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: page.loading ? qsTr("获取中…") : qsTr("强制刷新")
                    onClicked: page.reload(true)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Th.borderSubtle
        }

        // --- cards and details -------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                GridView {
                    id: grid
                    objectName: "versionsList"
                    anchors.fill: parent
                    anchors.margins: Th.pad
                    clip: true
                    cellWidth: 232
                    cellHeight: 116
                    model: releaseModel
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        id: versionCard
                        required property int index
                        required property string version
                        required property string date
                        required property int size
                        required property bool installed
                        required property string summary
                        required property string notes
                        required property string kindLabel

                        readonly property bool active: page.selected !== null
                                                       && page.selected.version === versionCard.version

                        width: 220
                        height: 104
                        radius: Th.radiusCard
                        color: cardHover.containsMouse ? Th.surfaceHover : Th.surface
                        border.width: 1
                        border.color: active ? Th.accent
                                             : (cardHover.containsMouse ? Th.borderStrong : Th.borderSubtle)

                        Behavior on color { ColorAnimation { duration: 120 } }

                        MouseArea {
                            id: cardHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: page.selected = {
                                "version": versionCard.version,
                                "date": versionCard.date,
                                "size": versionCard.size,
                                "installed": versionCard.installed,
                                "notes": versionCard.notes,
                                "kindLabel": versionCard.kindLabel
                            }
                        }

                        Column {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: Th.space3
                            spacing: Th.space1

                            Row {
                                spacing: Th.space2

                                Text {
                                    text: versionCard.version
                                    color: Th.text
                                    font.pixelSize: Th.fontSubtitle
                                    font.bold: true
                                }
                                StatusChip {
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: versionCard.kindLabel !== ""
                                    text: versionCard.kindLabel
                                    kind: "muted"
                                }
                            }

                            Text {
                                width: parent.width
                                text: versionCard.summary !== "" ? versionCard.summary : qsTr("（官方未提供说明）")
                                color: Th.textDim
                                font.pixelSize: Th.fontCaption
                                elide: Text.ElideRight
                                maximumLineCount: 2
                                wrapMode: Text.WordWrap
                            }
                        }

                        Row {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.leftMargin: Th.space3
                            anchors.rightMargin: Th.space3
                            anchors.bottomMargin: Th.space2
                            spacing: Th.space2

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: (versionCard.date ? versionCard.date : "-") +
                                      (versionCard.size ? "   " + (versionCard.size / 1048576).toFixed(1) + " MB" : "")
                                color: Th.textMuted
                                font.pixelSize: Th.fontMicro
                            }

                            Item { width: 1; height: 1 }

                            StatusChip {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: versionCard.installed
                                text: qsTr("已下载")
                                kind: "ok"
                            }
                        }
                    }
                }

                Column {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 80, 620)
                    spacing: 12
                    visible: releaseModel.count === 0

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: page.loading ? qsTr("正在获取版本列表…") : qsTr("还没有版本列表")
                        color: Th.text
                        font.pixelSize: Th.fontTitle
                        font.bold: true
                    }
                    Text {
                        width: parent.width
                        text: page.loading
                              ? qsTr("首次获取需要联网；之后会立即显示本地缓存。")
                              : qsTr("点「强制刷新」从官方源获取；已下载的版本在本地，离线也能用。")
                        color: Th.textMuted
                        font.pixelSize: Th.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: Th.borderSubtle
            }

            // --- detail panel --------------------------------------------
            Item {
                Layout.preferredWidth: page.panelWidth
                Layout.fillHeight: true

                Rectangle {
                    anchors.fill: parent
                    color: Th.surface

                    Text {
                        anchors.centerIn: parent
                        width: parent.width - Th.space6
                        visible: page.selected === null
                        text: qsTr("点一个版本卡片，这里显示它的完整更新说明与操作")
                        color: Th.textDim
                        font.pixelSize: Th.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Th.space4
                        spacing: Th.space3
                        visible: page.selected !== null

                        Row {
                            spacing: Th.space2

                            Text {
                                text: page.selected ? page.selected.version : ""
                                color: Th.text
                                font.pixelSize: Th.fontHeading
                                font.bold: true
                            }
                            StatusChip {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: page.selected && page.selected.kindLabel !== ""
                                text: page.selected ? page.selected.kindLabel : ""
                                kind: "muted"
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: page.selected
                                  ? ((page.selected.date || "-") + "   ·   " +
                                     (page.selected.size ? (page.selected.size / 1048576).toFixed(1) + " MB" : "-") +
                                     (page.selected.installed ? qsTr("   ·   已下载到本地") : ""))
                                  : ""
                            color: Th.textMuted
                            font.pixelSize: Th.fontCaption
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

                        Flickable {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 220
                            clip: true
                            contentWidth: width
                            contentHeight: notesText.height
                            boundsBehavior: Flickable.StopAtBounds

                            Text {
                                id: notesText
                                width: parent.width
                                text: page.selected ? page.selected.notes : ""
                                color: Th.text
                                font.pixelSize: Th.fontSmall
                                lineHeight: 1.3
                                wrapMode: Text.WordWrap
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Th.space2

                            BarButton {
                                text: page.selected && page.selected.installed ? qsTr("重新下载") : qsTr("下载")
                                primary: true
                                enabled: page.selected !== null
                                onClicked: bridge.downloadVersion(page.kind, page.selected.version)
                            }
                            BarButton {
                                text: qsTr("复制链接")
                                enabled: page.selected !== null
                                onClicked: bridge.copyText(
                                    bridge.releaseUrl(page.kind, page.selected ? page.selected.version : ""))
                            }
                            BarButton {
                                text: "Release 页"
                                enabled: page.selected !== null
                                onClicked: bridge.openUrl(
                                    bridge.releaseUrl(page.kind, page.selected ? page.selected.version : ""))
                            }
                            BarButton {
                                text: qsTr("删除本地")
                                danger: true
                                enabled: page.selected !== null && page.selected.installed
                                onClicked: confirmDialog.open()
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

                        Text {
                            text: qsTr("直接应用到游戏")
                            color: Th.textMuted
                            font.pixelSize: Th.fontCaption
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Th.space2

                            ComboBox {
                                id: gamePicker
                                Layout.fillWidth: true
                                implicitHeight: 30
                                font.pixelSize: Th.fontSmall
                                model: page.gameChoices
                                textRole: "label"
                                valueRole: "key"
                                onActivated: page.chosenGame = currentValue

                                background: Rectangle {
                                    radius: Th.radiusControl
                                    color: Th.surfaceAlt
                                    border.width: 1
                                    border.color: gamePicker.activeFocus ? Th.accent : Th.border
                                }
                                contentItem: Text {
                                    leftPadding: Th.space3
                                    text: page.chosenGame === "" ? qsTr("选择游戏…") : gamePicker.displayText
                                    color: page.chosenGame === "" ? Th.textDim : Th.text
                                    font.pixelSize: Th.fontSmall
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }
                                indicator: Text {
                                    x: gamePicker.width - width - Th.space2
                                    y: (gamePicker.height - height) / 2
                                    text: "▾"
                                    color: Th.textMuted
                                    font.pixelSize: Th.fontSmall
                                }
                                popup: Popup {
                                    y: gamePicker.height + Th.space1
                                    width: gamePicker.width
                                    implicitHeight: Math.min(contentItem.implicitHeight + Th.space2, 260)
                                    padding: Th.space1
                                    background: Rectangle {
                                        radius: Th.radiusControl
                                        color: Th.surfaceAlt
                                        border.width: 1
                                        border.color: Th.borderStrong
                                    }
                                    contentItem: ListView {
                                        implicitHeight: contentHeight
                                        model: gamePicker.popup.visible ? gamePicker.delegateModel : null
                                        clip: true
                                        delegate: ItemDelegate {
                                            width: gamePicker.width - Th.space2
                                            contentItem: Text {
                                                text: modelData.label
                                                color: Th.text
                                                font.pixelSize: Th.fontSmall
                                                verticalAlignment: Text.AlignVCenter
                                                elide: Text.ElideRight
                                            }
                                            background: Rectangle {
                                                radius: Th.radiusControl - 2
                                                color: parent.hovered ? Th.surfaceHover : "transparent"
                                            }
                                        }
                                    }
                                }
                            }

                            BarButton {
                                text: qsTr("应用")
                                primary: true
                                enabled: page.chosenGame !== "" && page.selected !== null
                                onClicked: bridge.installDxvk(page.chosenGame, page.kind,
                                                              page.selected.version)
                            }
                        }
                    }
                }
            }
        }

        // --- download progress -------------------------------------------
        Rectangle {
            id: progress
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 28 : 0
            color: Th.surface
            visible: false

            property real value: 0
            property string label: ""

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                height: 2
                width: parent.width * Math.max(0, Math.min(1, progress.value))
                color: Th.accent
            }
            Text {
                anchors.left: parent.left
                anchors.leftMargin: Th.pad
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("下载中…  ") + progress.label
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
            }
        }
    }

    // Deletion is irreversible locally (re-download brings it back, so the
    // copy stays honest about that), but still worth one confirmation.
    // Fully themed: the Basic style's default dialog shell mixes palette
    // colours and rendered the body text nearly invisible on the dark theme.
    Dialog {
        id: confirmDialog
        modal: true
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 400
        padding: Th.space4

        Overlay.modal: Rectangle { color: "#99000000" }

        background: Rectangle {
            color: Th.surface
            radius: Th.radiusPanel
            border.width: 1
            border.color: Th.borderStrong
        }

        header: Text {
            text: qsTr("删除本地版本")
            color: Th.text
            font.pixelSize: Th.fontHeading
            font.bold: true
            topPadding: Th.space4
            leftPadding: Th.space4
            rightPadding: Th.space4
            bottomPadding: Th.space2
        }

        contentItem: Text {
            text: page.selected
                  ? qsTr("把 %1 从本地缓存删除？\n\n已安装到游戏的 DLL 不受影响；之后想用可随时重新下载。").arg(page.selected.version)
                  : ""
            color: Th.text
            font.pixelSize: Th.fontBody
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
        }

        footer: DialogButtonBox {
            background: Rectangle { color: "transparent" }
            alignment: Qt.AlignRight
            spacing: Th.space2
            topPadding: 0

            // Danger action: solid red, white text (GitHub destructive style).
            Button {
                id: deleteConfirmButton
                text: qsTr("删除")
                onClicked: {
                    confirmDialog.accept()
                    bridge.removeVersion(page.kind, page.selected ? page.selected.version : "")
                }
                contentItem: Text {
                    text: deleteConfirmButton.text
                    color: "#ffffff"
                    font.pixelSize: Th.fontSmall
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: Th.radiusControl
                    color: deleteConfirmButton.hovered ? "#f85149" : "#b62324"
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }
            Button {
                id: cancelConfirmButton
                text: qsTr("取消")
                onClicked: confirmDialog.reject()
                contentItem: Text {
                    text: cancelConfirmButton.text
                    color: Th.text
                    font.pixelSize: Th.fontSmall
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: Th.radiusControl
                    color: cancelConfirmButton.hovered ? Th.surfaceHover : Th.surfaceAlt
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }
        }
    }

    // --- shared toolbar pieces (same shapes as the games page) -----------
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
        id: seg
        padding: 6
        checkable: true
        background: Rectangle {
            radius: Th.radiusControl - 2
            color: seg.checked ? Th.accentDark : (seg.hovered ? Th.surfaceHover : "transparent")
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        contentItem: Text {
            text: seg.text
            color: seg.checked ? "#ffffff" : Th.textMuted
            font.pixelSize: Th.fontSmall
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    component BarButton: Button {
        id: bar
        property bool primary: false
        // Destructive actions render as a red button, matching the danger
        // style of the confirmation dialog's 删除.
        property bool danger: false
        padding: 6
        opacity: enabled ? 1.0 : 0.45
        background: Rectangle {
            radius: Th.radiusControl
            color: bar.danger
                 ? (bar.hovered ? "#f85149" : "#b62324")
                 : bar.primary
                 ? (bar.hovered ? Th.primaryHover : Th.primary)
                 : (bar.hovered ? Th.surfaceHover : Th.surfaceAlt)
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        contentItem: Text {
            text: bar.text
            color: bar.danger || bar.primary ? Th.primaryText : Th.text
            font.pixelSize: Th.fontSmall
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    ListModel {
        id: releaseModel
        objectName: "releaseModel"
    }
}
