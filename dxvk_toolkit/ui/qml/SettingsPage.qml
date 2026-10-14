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
        font.pixelSize: Th.fontSubtitle
        font.bold: true
    }

    component Hint: Text {
        color: Th.textMuted
        font.pixelSize: Th.fontCaption
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
            font.pixelSize: Th.fontBody
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

        // Qt draws its own ComboBox and Switch in the light palette, which put
    // white boxes and square corners in the middle of the dark interface.
    // Both are drawn here instead, popup list included.
    component DarkCombo: ComboBox {
        id: combo
        implicitHeight: 30
        font.pixelSize: Th.fontSmall

        background: Rectangle {
            radius: Th.radiusControl
            color: Th.surfaceAlt
            border.width: 1
            border.color: combo.hovered || combo.activeFocus ? Th.borderStrong : Th.border
            Behavior on border.color { ColorAnimation { duration: 120 } }
        }
        contentItem: Text {
            leftPadding: Th.space3
            rightPadding: Th.space5
            text: combo.displayText
            color: Th.text
            font.pixelSize: Th.fontSmall
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Text {
            x: combo.width - width - Th.space2
            y: (combo.height - height) / 2
            text: "▾"
            color: Th.textMuted
            font.pixelSize: Th.fontSmall
        }
        popup: Popup {
            y: combo.height + Th.space1
            width: combo.width
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
                model: combo.popup.visible ? combo.delegateModel : null
                clip: true

                delegate: ItemDelegate {
                    width: combo.width - Th.space2
                    contentItem: Text {
                        // Object models (the download source list) carry a label
                        // field; a plain string list has modelData itself.
                        text: combo.textRole ? model[combo.textRole] : modelData
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

    component DarkSwitch: Switch {
        id: sw
        // Basic style 的 implicitWidth 公式只算 background/contentItem，
        // 不含 indicator：contentItem 置空后控件塌缩到 padding*2 = 12px，
        // 40px 轨道向右溢出、窄窗口下被窗口边裁掉。将控件钉死为轨道
        // 尺寸并归零 padding，让 anchors.right 的语义落在轨道右缘上。
        implicitWidth: 40
        implicitHeight: 24
        padding: 0

        indicator: Rectangle {
            implicitWidth: 40
            implicitHeight: 22
            x: 0
            y: (sw.height - height) / 2
            radius: 11
            color: sw.checked ? Th.accentDark : Th.surfaceAlt
            border.width: 1
            border.color: sw.checked ? Th.accent : Th.border

            Behavior on color { ColorAnimation { duration: 120 } }

            Rectangle {
                width: 16
                height: 16
                radius: 8
                y: 2
                x: sw.checked ? parent.width - width - 3 : 3
                color: sw.checked ? "#ffffff" : Th.textMuted
                Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
        }
        contentItem: Item {}
    }

    Column {
            id: content
            // Settings read badly when a row stretches across the whole
            // window: cap the measure and centre it, like every settings page.
            // Left aligned and full width: the cards are the grouping, so the
            // column does not need to be narrowed or centred.
            x: Th.pad
            y: Th.pad
            width: parent.width - Th.pad * 2
            spacing: Th.space4

            // --- offline ---------------------------------------------------
            Card {
                height: 92
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    Item {
                        width: parent.width
                        height: 28

                        SectionTitle {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: qsTr("离线模式")
                        }
                        DarkSwitch {
                            id: offlineSwitch
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            checked: bridge.getSetting("offline_mode") === true
                            onToggled: bridge.setSetting("offline_mode", checked)
                        }
                    }
                    Hint {
                        width: parent.width
                        text: qsTr("打开后程序不发起任何网络请求：版本列表与封面只使用本地已有内容，下载会直接提示离线模式已开启。")
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

                    SectionTitle { text: qsTr("网络与下载源") }

                    Row {
                        width: parent.width
                        spacing: 8

                        Text {
                            text: qsTr("代理")
                            color: Th.textMuted
                            font.pixelSize: Th.fontBody
                            width: 42
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        DarkCombo {
                            id: proxyMode
                            width: 130
                            model: [qsTr("自动"), qsTr("直连"), qsTr("自定义")]
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
                            text: qsTr("探测本地代理")
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
                            text: qsTr("下载源")
                            color: Th.textMuted
                            font.pixelSize: Th.fontBody
                            width: 42
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        DarkCombo {
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
                            text: qsTr("官方源被墙时自动改用镜像")
                            elide: Text.ElideRight
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 8

                        Button {
                            text: qsTr("测试连接")
                            padding: 8
                            onClicked: {
                                netStatus.text = qsTr("测试中…")
                                // @Slot(str, bool): Qt cannot see Python
                                // defaults, so pass both arguments.
                                bridge.loadVersions("dxvk", false)
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
                                font.pixelSize: Th.fontBody
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Text {
                            id: netStatus
                            width: parent.width - 130
                            anchors.verticalCenter: parent.verticalCenter
                            text: qsTr("点「测试连接」会真实拉取一次版本列表")
                            color: Th.textDim
                            font.pixelSize: Th.fontCaption
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            // --- generated config file -------------------------------------
            Card {
                height: 92
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    Item {
                        width: parent.width
                        height: 28

                        SectionTitle {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: qsTr("导出的 dxvk.conf")
                        }
                        DarkSwitch {
                            id: commentsSwitch
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            checked: bridge.getSetting("conf_comments") !== false
                            onToggled: bridge.setSetting("conf_comments", checked)
                        }
                    }
                    Hint {
                        width: parent.width
                        text: qsTr("开启后每个选项上方会写入中文说明（与原版工具一致）；关闭则只输出选项本身。预览与导出使用同一份内容。")
                    }
                }
            }

            // --- interface language ---------------------------------------
            // ui_lang drives the Qt translator loaded at startup (§28); the
            // option explanation language (docs_language) stays independent,
            // so an English interface with Chinese notes is allowed.
            Card {
                height: 92
                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    Item {
                        width: parent.width
                        height: 28

                        SectionTitle {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: qsTr("界面语言")
                        }
                        DarkCombo {
                            id: langCombo
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: 160
                            model: [qsTr("简体中文"), "English"]
                            currentIndex: bridge.getSetting("ui_lang") === "en" ? 1 : 0
                            onActivated: bridge.setSetting("ui_lang",
                                                           currentIndex === 1 ? "en" : "zh")
                        }
                    }
                    Hint {
                        width: parent.width
                        text: qsTr("切换界面文字，重启应用后生效；选项说明的语言独立设置，互不影响。")
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

                    SectionTitle { text: qsTr("数据目录") }
                    Hint {
                        width: parent.width
                        text: bridge.dataRoot()
                        color: Th.textMuted
                    }
                    Hint {
                        width: parent.width
                        text: qsTr("已下载的版本放在这里；游戏目录只会出现 DXVK 的 DLL 和安装时生成的 .bkp 备份。")
                        color: Th.textDim
                    }
                    FlatButton {
                        text: qsTr("打开数据目录")
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

                    SectionTitle { text: qsTr("官方资源") }

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

                    SectionTitle { text: qsTr("鸣谢") }

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
                                            font.pixelSize: Th.fontBody
                                            font.bold: true
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modelData.author
                                            color: Th.textMuted
                                            font.pixelSize: Th.fontCaption
                                        }
                                        Item { width: 1; height: 1 }
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.role
                                        color: Th.textDim
                                        font.pixelSize: Th.fontCaption
                                        wrapMode: Text.WordWrap
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: qsTr("许可：%1").arg(modelData.license)
                                        color: Th.textDim
                                        font.pixelSize: Th.fontMicro
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
                        text: qsTr("查看完整第三方声明")
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

                    SectionTitle { text: qsTr("关于") }
                    Hint {
                        width: parent.width
                        text: qsTr("DXVK Version Manager · Python edition v%1\n界面：PySide6 + QML（Qt Quick）；核心逻辑为与界面无关的纯 Python 标准库实现。中文选项说明由本项目翻译，英文原文来自 DXVK 的 dxvk.conf。").arg(bridge.appVersion())
                    }
                }
            }
        }
    }
}