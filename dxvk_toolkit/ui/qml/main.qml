import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

ApplicationWindow {
    id: window
    visible: true
    width: 1360
    height: 860
    minimumWidth: 900
    minimumHeight: 600
    title: "DXVK Version Manager"
    color: Th.bg

    property int currentPage: 0
    property bool busy: false
    property string statusText: "就绪"
    property string statusKind: "info"

    readonly property var pages: [
        { label: "游戏库", hint: "扫描并管理游戏" },
        { label: "版本库", hint: "下载 DXVK 版本" },
        { label: "配置", hint: "生成 dxvk.conf" },
        { label: "设置", hint: "离线模式与数据目录" }
    ]

    Connections {
        target: bridge
        function onStatusMessage(text, kind) {
            window.statusText = text
            window.statusKind = kind
        }
        function onBusyChanged(value) { window.busy = value }
    }

    // A light scan on start-up: it only reads the launcher manifests, so the
    // window fills immediately without touching the network or the disk hard.
    Component.onCompleted: Qt.callLater(bridge.scanGames)

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- top bar -----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            color: Th.surface

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 8

                Text {
                    text: "DXVK"
                    color: Th.text
                    font.pixelSize: Th.fontHeading
                    font.bold: true
                    Layout.rightMargin: 14
                }

                Item {
                    Layout.preferredWidth: tabRow.width
                    Layout.fillHeight: true

                    Row {
                        id: tabRow
                        anchors.fill: parent
                        spacing: 8

                        Repeater {
                            id: tabRepeater
                            model: window.pages
                            delegate: Item {
                                width: tabLabel.implicitWidth + 30
                                height: tabRow.height

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.topMargin: 12
                                    anchors.bottomMargin: 12
                                    radius: Th.radiusSmall
                                    color: window.currentPage === index ? Th.surfaceHover
                                           : (tabHover.hovered ? Th.surfaceAlt : "transparent")

                                    Behavior on color { ColorAnimation { duration: 120 } }
                                }

                                Text {
                                    id: tabLabel
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: window.currentPage === index ? Th.text : Th.textMuted
                                    font.pixelSize: Th.fontSubtitle
                                    font.bold: window.currentPage === index

                                    Behavior on color { ColorAnimation { duration: 140 } }
                                }

                                MouseArea {
                                    id: tabHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: window.currentPage = index
                                }
                            }
                        }
                    }

                    // One underline that slides to the active tab.
                    Rectangle {
                        id: tabUnderline
                        height: 2
                        radius: Th.radiusHairline
                        color: Th.accent
                        y: tabRow.height - 2
                        x: {
                            var tab = tabRepeater.itemAt(window.currentPage)
                            return tab ? tab.x + 9 : 0
                        }
                        width: {
                            var tab = tabRepeater.itemAt(window.currentPage)
                            return tab ? tab.width - 18 : 0
                        }
                        Behavior on x {
                            NumberAnimation { duration: 190; easing.type: Easing.OutCubic }
                        }
                        Behavior on width {
                            NumberAnimation { duration: 190; easing.type: Easing.OutCubic }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: window.pages[window.currentPage].hint
                    color: Th.textDim
                    font.pixelSize: Th.fontCaption
                }
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Th.border }

        // --- pages -------------------------------------------------------
        StackLayout {
            id: pageStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.currentPage

            onCurrentIndexChanged: pageFade.restart()
            NumberAnimation {
                id: pageFade
                target: pageStack
                property: "opacity"
                from: 0.25
                to: 1.0
                duration: 190
                easing.type: Easing.OutCubic
            }

            GamesPage {}
            VersionsPage {}
            ConfigPage {}
            SettingsPage {}
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Th.border }

        // --- status bar --------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            color: Th.surface

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: window.statusText
                color: window.statusKind === "error" ? Th.error
                     : window.statusKind === "ok" ? Th.ok
                     : window.statusKind === "warn" ? Th.warn
                     : Th.textMuted
                font.pixelSize: Th.fontBody
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                BusyIndicator {
                    running: window.busy
                    visible: window.busy
                    width: 16
                    height: 16
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: window.busy ? "处理中…" : "v" + bridge.appVersion()
                    color: Th.textDim
                    font.pixelSize: Th.fontCaption
                }
            }
        }
    }
}
