import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

Item {
    id: page
    objectName: "versionsPage"

    property string kind: "dxvk"
    property bool loading: false

    ListModel { id: releaseModel; objectName: "releaseModel" }
    ListModel { id: localModel }

    function reload() {
        releaseModel.clear()
        page.loading = true
        bridge.loadVersions(page.kind)
    }

    Connections {
        target: bridge
        function onVersionsReady(payload) {
            page.loading = false
            if (payload.kind !== page.kind)
                return
            releaseModel.clear()
            var releases = payload.releases || []
            for (var i = 0; i < releases.length; i++) {
                var r = releases[i]
                releaseModel.append({
                    version: r.version,
                    label: r.label,
                    date: r.date,
                    size: r.size,
                    installed: (payload.installed || []).indexOf(
                        page.kind === "gplasync" ? r.version.replace(/^v/, "") : r.version) !== -1
                })
            }
        }
        function onLocalVersionsReady(payload) {
            localModel.clear()
            var list = (payload[page.kind] || [])
            for (var i = 0; i < list.length; i++)
                localModel.append({ version: list[i] })
        }
        function onProgressChanged(fraction, label) {
            progress.visible = fraction >= 0
            progress.value = fraction >= 0 ? fraction : 0
            progress.label = label
        }
    }

    Component.onCompleted: bridge.loadLocalVersions()

    ColumnLayout {
        id: column
        objectName: "versionsColumn"
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            color: Th.surface

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Th.pad
                anchors.rightMargin: Th.pad
                spacing: 8

                Button {
                    text: "官方 DXVK"
                    checkable: true
                    checked: page.kind === "dxvk"
                    onClicked: { page.kind = "dxvk"; bridge.loadLocalVersions() }
                    background: Rectangle { radius: Th.radiusSmall
                                            color: parent.checked ? Th.accentDark
                                                 : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt) }
                    contentItem: Text { text: parent.text; color: parent.checked ? "#ffffff" : Th.textMuted
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
                }
                Button {
                    text: "DXVK-GPLAsync"
                    checkable: true
                    checked: page.kind === "gplasync"
                    onClicked: { page.kind = "gplasync"; bridge.loadLocalVersions() }
                    background: Rectangle { radius: Th.radiusSmall
                                            color: parent.checked ? Th.accentDark
                                                 : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt) }
                    contentItem: Text { text: parent.text; color: parent.checked ? "#ffffff" : Th.textMuted
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "已下载 " + localModel.count + " 个"
                    color: Th.textMuted
                    font.pixelSize: 12
                }

                Button {
                    text: page.loading ? "获取中…" : "刷新列表"
                    padding: 8
                    enabled: !page.loading
                    onClicked: page.reload()
                    background: Rectangle { radius: Th.radiusSmall
                                            color: parent.hovered ? Th.primaryHover : Th.primary }
                    contentItem: Text { text: parent.text; color: Th.primaryText; font.bold: true
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter }
                }
            }
        }

        Rectangle {
            id: progress
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 26 : 0
            color: Th.surfaceAlt
            visible: false
            property string label: ""
            property real value: 0

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * Math.max(0, Math.min(1, progress.value))
                color: Th.accentDark
            }
            Text {
                anchors.centerIn: parent
                text: parent.label
                color: Th.text
                font.pixelSize: 11
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
            id: list
            objectName: "versionsList"
            anchors.fill: parent
            clip: true
            model: releaseModel
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
                                  duration: 200; easing.type: Easing.OutCubic }
            }

            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function (event) {
                    var delta = event.pixelDelta.y !== 0
                              ? event.pixelDelta.y * 2
                              : (event.angleDelta.y / 120) * 54 * 3
                    var limit = Math.max(0, list.contentHeight - list.height)
                    list.contentY = Math.max(0, Math.min(limit, list.contentY - delta))
                    event.accepted = true
                }
            }

            delegate: Rectangle {
                required property string version
                required property string label
                required property string date
                required property int size
                required property bool installed

                width: list.width
                height: 52
                color: index % 2 === 0 ? Th.surface : Th.surfaceAlt

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Th.pad
                    anchors.rightMargin: Th.pad
                    spacing: 12

                    Text {
                        text: version
                        color: Th.text
                        font.pixelSize: 13
                        font.bold: true
                        Layout.preferredWidth: 120
                    }
                    Text {
                        text: date ? date : "-"
                        color: Th.textMuted
                        font.pixelSize: 12
                        Layout.preferredWidth: 110
                    }
                    Text {
                        text: size ? (size / 1048576).toFixed(1) + " MB" : "-"
                        color: Th.textMuted
                        font.pixelSize: 12
                        Layout.preferredWidth: 90
                    }
                    Text {
                        text: installed ? "已下载" : ""
                        color: Th.ok
                        font.pixelSize: 12
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: installed ? "重新下载" : "下载"
                        onClicked: bridge.downloadVersion(page.kind, version)
                        background: Rectangle { radius: Th.radiusSmall
                                                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt }
                        contentItem: Text { text: parent.text; color: Th.text; font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter }
                    }
                }
            }
        }

            // Empty state floats above the list, so the two never fight over
            // the layout's height (which squeezed the list to a few pixels).
            Column {
                anchors.centerIn: parent
                width: Math.min(parent.width - 80, 620)
                spacing: 12
                visible: releaseModel.count === 0

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: page.loading ? "正在获取版本列表…" : "还没有版本列表"
                    color: Th.text
                    font.pixelSize: 16
                    font.bold: true
                }
                Text {
                    width: parent.width
                    text: "点「刷新列表」从官方源获取（这是唯一需要联网的操作）。已下载的版本在本地，离线也能用。"
                    color: Th.textMuted
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}