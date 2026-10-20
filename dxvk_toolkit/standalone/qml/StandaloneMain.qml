import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../ui/qml/theme.js" as Th
import "../../ui/qml" as Shared

// The standalone configurator's window.
//
// It shows one thing: the option catalogue on the left, the generated
// dxvk.conf on the right. There is no game library, no version list and no
// settings page - the tool's whole job is "given a dxvk.conf, produce a
// customised one".
//
// The components it borrows from the full application (ConfigToolbar,
// ConfigContextBar, ConfigRail, ConfigOptionList, ConfigPresetDialog) know
// nothing about games, so they are used verbatim and cannot drift apart.
// Only the two strips whose meaning differs - the file bar and the preview -
// are written here.
ApplicationWindow {
    id: window
    visible: true
    width: 1360
    height: 860
    minimumWidth: 900
    minimumHeight: 600
    title: qsTr("DXVK 配置生成器")
    color: Th.bg

    property string statusText: qsTr("就绪")
    property string statusKind: "info"
    property string currentFileName: ""
    property string uiLang: bridge.getSetting("ui_lang") || "zh"

    Connections {
        target: bridge
        function onStatusMessage(text, kind) {
            window.statusText = text
            window.statusKind = kind
        }
        function onFileOpened(path, name) {
            window.currentFileName = name
        }
        function onLanguageChanged(lang) {
            window.uiLang = lang
            // The generated file carries the option explanations, so the
            // preview has to be rebuilt with the new language.
            configPage.refreshPreview()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- file bar ------------------------------------------------------
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

                Text {
                    text: qsTr("配置生成器")
                    color: Th.textMuted
                    font.pixelSize: Th.fontSubtitle
                    Layout.rightMargin: 18
                }

                Text {
                    text: window.currentFileName
                    color: window.currentFileName === "" ? Th.textDim : Th.text
                    font.pixelSize: Th.fontBody
                    elide: Text.ElideMiddle
                    Layout.maximumWidth: 320
                }

                Item { Layout.fillWidth: true }

                // Language switch. The configurator is a one-purpose tool, so
                // the interface language and the option explanations travel
                // together - one switch, no settings page.
                Shared.MiniButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: window.uiLang === "en" ? "中文" : "English"
                    onClicked: bridge.setLanguage(window.uiLang === "en" ? "zh" : "en")
                }

                Shared.MiniButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("打开文件…")
                    onClicked: bridge.importConfig()
                }

                Shared.MiniButton {
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("保存")
                    visible: window.currentFileName !== ""
                    onClicked: bridge.saveFile()
                }
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Th.border }

        // --- the editor ----------------------------------------------------
        ConfiguratorPage {
            id: configPage
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Th.border }

        // --- status bar ----------------------------------------------------
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
                elide: Text.ElideRight
                anchors.right: versionLabel.left
                anchors.rightMargin: Th.space2
            }

            Text {
                id: versionLabel
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: "v" + bridge.appVersion()
                color: Th.textDim
                font.pixelSize: Th.fontCaption
            }
        }
    }
}
