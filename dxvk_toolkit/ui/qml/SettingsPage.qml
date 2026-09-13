import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

Item {
    id: page

    component Card: Rectangle {
        width: parent ? parent.width : 0
        radius: Th.radius
        color: Th.surface
        border.color: Th.border
    }

    component SectionTitle: Text {
        color: Th.text
        font.pixelSize: 14
        font.bold: true
    }

    component Hint: Text {
        color: Th.textMuted
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }

    component FlatButton: Button {
        background: Rectangle {
            radius: Th.radiusSmall
            color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        contentItem: Text {
            text: parent.text
            color: Th.text
            font.pixelSize: 12
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Flickable {
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: content.height + Th.pad * 2
        boundsBehavior: Flickable.StopAtBounds

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

        Column {
            id: content
            x: Th.pad
            y: Th.pad
            width: parent.width - Th.pad * 2
            spacing: 16

            // --- offline ---------------------------------------------------
            Card {
                height: 96
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    Row {
                        width: parent.width
                        SectionTitle { text: "离线模式" }
                        Switch {
                            id: offlineSwitch
                            anchors.verticalCenter: parent.verticalCenter
                            x: parent.width - width
                            checked: bridge.getSetting("offline_mode") === true
                            onToggled: bridge.setSetting("offline_mode", checked)
                        }
                    }
                    Hint {
                        width: parent.width
                        text: "打开后程序不发起任何网络请求：版本列表与封面只使用本地已有内容，下载会直接提示离线模式已开启。"
                    }
                }
            }

            // --- network ---------------------------------------------------
            Card {
                height: 200
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    SectionTitle { text: "网络与下载源" }

                    Row {
                        width: parent.width
                        spacing: 8

                        Text {
                            text: "代理"
                            color: Th.textMuted
                            font.pixelSize: 12
                            width: 42
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        ComboBox {
                            id: proxyMode
                            width: 130
                            model: ["自动", "直连", "自定义"]
                            currentIndex: {
                                var mode = bridge.getSetting("proxy_mode")
                                return mode === "direct" ? 1 : (mode === "custom" ? 2 : 0)
                            }
                            onActivated: bridge.setSetting("proxy_mode",
                                                           ["auto", "direct", "custom"][currentIndex])
                        }

                        TextField {
                            id: proxyUrl
                            width: parent.width - 130 - 42 - 130 - 32
                            text: bridge.getSetting("proxy_url") || ""
                            placeholderText: "http://127.0.0.1:7897"
                            color: Th.text
                            placeholderTextColor: Th.textDim
                            background: Rectangle {
                                radius: Th.radiusControl
                                color: Th.surfaceAlt
                                border.color: proxyUrl.activeFocus ? Th.accent : Th.border
                            }
                            onEditingFinished: bridge.setSetting("proxy_url", text)
                        }

                        FlatButton {
                            text: "探测本地代理"
                            onClicked: {
                                var found = bridge.probeLocalProxy()
                                if (found !== "") {
                                    proxyUrl.text = found
                                    proxyMode.currentIndex = 2
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 8

                        Text {
                            text: "下载源"
                            color: Th.textMuted
                            font.pixelSize: 12
                            width: 42
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        ComboBox {
                            id: sourceBox
                            width: 300
                            model: bridge.downloadSources()
                            textRole: "label"
                            valueRole: "value"
                            Component.onCompleted: {
                                var current = bridge.currentDownloadSource()
                                for (var i = 0; i < model.length; i++) {
                                    if (model[i].value === current) {
                                        currentIndex = i
                                        break
                                    }
                                }
                            }
                            onActivated: bridge.setDownloadSource(currentValue)
                        }

                        Hint {
                            width: parent.width - 350
                            anchors.verticalCenter: parent.verticalCenter
                            text: "官方源被墙时自动改用镜像"
                            elide: Text.ElideRight
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 8

                        Button {
                            text: "测试连接"
                            padding: 8
                            onClicked: {
                                netStatus.text = "测试中…"
                                bridge.loadVersions("dxvk")
                            }
                            background: Rectangle {
                                radius: Th.radiusSmall
                                color: parent.hovered ? Th.primaryHover : Th.primary
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                            contentItem: Text {
                                text: parent.text
                                color: Th.primaryText
                                font.bold: true
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Text {
                            id: netStatus
                            width: parent.width - 130
                            anchors.verticalCenter: parent.verticalCenter
                            text: "点「测试连接」会真实拉取一次版本列表"
                            color: Th.textDim
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            // --- data ------------------------------------------------------
            Card {
                height: 132
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    SectionTitle { text: "数据目录" }
                    Hint {
                        width: parent.width
                        text: bridge.dataRoot()
                        color: Th.textMuted
                    }
                    Hint {
                        width: parent.width
                        text: "已下载的版本放在这里；游戏目录只会出现 DXVK 的 DLL 和安装时生成的 .bkp 备份。"
                        color: Th.textDim
                    }
                    FlatButton {
                        text: "打开数据目录"
                        onClicked: bridge.openDataFolder()
                    }
                }
            }

            // --- official resources ----------------------------------------
            Card {
                height: 118
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    SectionTitle { text: "官方资源" }

                    Flow {
                        width: parent.width
                        spacing: 8

                        Repeater {
                            model: bridge.officialLinks()
                            delegate: FlatButton {
                                text: modelData.label
                                onClicked: bridge.openUrl(modelData.url)
                            }
                        }
                    }
                }
            }

            // --- credits ---------------------------------------------------
            Card {
                height: creditsColumn.height + 60
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    SectionTitle { text: "鸣谢" }

                    Column {
                        id: creditsColumn
                        width: parent.width
                        spacing: 8

                        Repeater {
                            model: bridge.credits()
                            delegate: Rectangle {
                                width: creditsColumn.width
                                height: 62
                                radius: Th.radiusSmall
                                color: Th.surfaceAlt

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 4

                                    Row {
                                        width: parent.width
                                        spacing: 8

                                        Text {
                                            text: modelData.name
                                            color: Th.text
                                            font.pixelSize: 13
                                            font.bold: true
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modelData.author
                                            color: Th.textMuted
                                            font.pixelSize: 11
                                        }
                                        Item { width: 1; height: 1 }
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.role
                                        color: Th.textDim
                                        font.pixelSize: 11
                                        wrapMode: Text.WordWrap
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: "许可：" + modelData.license
                                        color: Th.textDim
                                        font.pixelSize: 10
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: bridge.openUrl(modelData.url)
                                }
                            }
                        }
                    }

                    FlatButton {
                        text: "查看完整第三方声明"
                        onClicked: bridge.openFolder(bridge.noticesPath())
                    }
                }
            }

            // --- about -----------------------------------------------------
            Card {
                height: 120
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    SectionTitle { text: "关于" }
                    Hint {
                        width: parent.width
                        text: "DXVK Version Manager · Python edition v" + bridge.appVersion() +
                              "\n界面：PySide6 + QML（Qt Quick）；核心逻辑为与界面无关的纯 Python 标准库实现。" +
                              "中文选项说明由本项目翻译，英文原文来自 DXVK 的 dxvk.conf。"
                    }
                }
            }
        }
    }
}