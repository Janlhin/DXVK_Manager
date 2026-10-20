import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The top bar of the configuration page: search field, difficulty mode
// buttons and the import button, plus the option counter on the right.
Rectangle {
    id: toolbar

    property string mode: "simple"
    property string importMessage: ""
    property int selectedCount: 0
    // The standalone configurator opens .conf files through its own file
    // bar, so the import button is hidden there.
    property bool showImport: true

    // The search text belongs to the field; the page reads it back through
    // this read-only alias so the filter calls always use the same value.
    readonly property string searchText: search.text

    // The mode property already provides a modeChanged signal, so the
    // notification carries a different name.
    signal modeSelected(string value)
    signal searchChanged(string text)
    signal importRequested()

    height: 52
    color: Th.surface

    Row {
        anchors.left: parent.left
        anchors.leftMargin: Th.pad
        anchors.verticalCenter: parent.verticalCenter
        spacing: Th.space2

        TextField {
            id: search
            width: 220
            anchors.verticalCenter: parent.verticalCenter
            placeholderText: qsTr("搜索选项…")
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
            onTextEdited: toolbar.searchChanged(text)
        }

        Repeater {
            model: [
                { value: "simple", label: qsTr("简单") },
                { value: "advanced", label: qsTr("进阶") },
                { value: "full", label: qsTr("完全") }
            ]
            delegate: Button {
                required property var modelData
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.label
                padding: 6
                checkable: true
                checked: toolbar.mode === modelData.value
                onClicked: toolbar.modeSelected(modelData.value)
                background: Rectangle {
                    radius: Th.radiusControl
                    color: parent.checked ? Th.accentDark
                         : (parent.hovered ? Th.surfaceHover : Th.surfaceAlt)
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
        }

        Button {
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("导入 dxvk.conf…")
            padding: 6
            visible: toolbar.showImport
            onClicked: toolbar.importRequested()
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
    }

    Text {
        anchors.right: parent.right
        anchors.rightMargin: Th.pad
        anchors.verticalCenter: parent.verticalCenter
        text: toolbar.importMessage !== ""
              ? toolbar.importMessage
              : qsTr("共 %1 项，已选 %2").arg(configModel.optionCount).arg(toolbar.selectedCount)
        color: toolbar.importMessage !== "" ? Th.ok : Th.textMuted
        font.pixelSize: Th.fontCaption
        elide: Text.ElideRight
        width: Math.min(360, toolbar.width * 0.3)
        horizontalAlignment: Text.AlignRight
    }
}
