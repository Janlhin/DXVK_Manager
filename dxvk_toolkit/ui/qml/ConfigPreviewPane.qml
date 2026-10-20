import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The preview pane (right column): the generated dxvk.conf, the export
// buttons and the comments toggle.
//
// The preview is part of the page (it was removed once and immediately
// missed): it shows the live result while options are ticked, and
// exports from its own buttons.
Item {
    id: preview
    objectName: "previewPane"

    property string gameKey: ""
    property string gameName: ""

    // "game" (the full application) previews a file that will be written
    // into a game folder; "file" (the standalone configurator) previews the
    // .conf file that is open and writes it back.
    property string mode: "game"

    // Whether the write button is usable. The full application always can
    // (it opens a game picker); the standalone sets it to "a file is open".
    property bool writeEnabled: true

    signal writeRequested()
    signal gamePickerRequested()
    signal refreshRequested()

    Rectangle {
        id: previewBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 52
        color: Th.surface

        Text {
            id: previewTitle
            anchors.left: parent.left
            anchors.leftMargin: Th.space4
            // Bound to the controls row so longer interface languages
            // (English) elide the title instead of overlapping it.
            anchors.right: previewControls.left
            anchors.rightMargin: Th.space2
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: qsTr("dxvk.conf 预览")
            color: Th.text
            font.pixelSize: Th.fontSubtitle
            font.bold: true
        }

        Row {
            id: previewControls
            anchors.right: parent.right
            anchors.rightMargin: Th.space3
            anchors.verticalCenter: parent.verticalCenter
            spacing: Th.space2

            // §29: the comments toggle lives next to the result it
            // changes. getSetting returns undefined when the key was
            // never written, and the generator defaults it to True
            // (bridge.previewConfig), so treat "unset" as checked.
            Text {
                text: qsTr("带注释")
                color: Th.textMuted
                font.pixelSize: Th.fontCaption
                anchors.verticalCenter: parent.verticalCenter
            }
            DarkSwitch {
                id: commentsSwitch
                anchors.verticalCenter: parent.verticalCenter
                checked: bridge.getSetting("conf_comments") !== false
                onToggled: {
                    bridge.setSetting("conf_comments", checked)
                    preview.refreshRequested()
                }
            }

            Button {
                text: qsTr("复制")
                padding: 6
                onClicked: bridge.copyConfig()
                background: Rectangle {
                    radius: Th.radiusControl
                    color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Text {
                    text: parent.text
                    color: Th.text
                    font.pixelSize: Th.fontCaption
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                id: writeButton
                padding: 6
                // In "file" mode the button writes the result back to the
                // .conf file that is open, so it is only enabled when there
                // is one.
                text: preview.mode === "file"
                      ? qsTr("保存")
                      : (preview.gameKey !== "" ? qsTr("应用并写入 %1").arg(preview.gameName) : qsTr("写入游戏…"))
                enabled: preview.writeEnabled
                onClicked: {
                    if (preview.mode === "file")
                        preview.writeRequested()
                    else if (preview.gameKey !== "")
                        preview.writeRequested()
                    else
                        preview.gamePickerRequested()
                }
                background: Rectangle {
                    radius: Th.radiusControl
                    color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Text {
                    text: parent.text
                    color: Th.text
                    font.pixelSize: Th.fontCaption
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                text: qsTr("保存为文件…")
                padding: 6
                onClicked: bridge.exportConfig()
                background: Rectangle {
                    radius: Th.radiusControl
                    color: parent.hovered ? Th.primaryHover : Th.primary
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Text {
                    text: parent.text
                    color: Th.primaryText
                    font.pixelSize: Th.fontCaption
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

    Rectangle {
        id: previewLine
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: previewBar.bottom
        height: 1
        color: Th.borderSubtle
    }

    Text {
        id: previewHint
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Th.space3
        height: 32
        text: preview.mode === "file"
              ? qsTr("把文件放在游戏 exe 所在目录即可生效；也可以直接导出到任意位置。")
              : qsTr("和游戏 exe 放在同一目录即可生效；这里可以独立导出，不需要扫描游戏。")
        color: Th.textDim
        font.pixelSize: Th.fontCaption
        wrapMode: Text.WordWrap
    }

    Flickable {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: previewLine.bottom
        anchors.bottom: previewHint.top
        anchors.leftMargin: Th.space3
        anchors.rightMargin: Th.space3
        anchors.topMargin: Th.space2
        clip: true
        contentWidth: previewArea.paintedWidth
        contentHeight: previewArea.paintedHeight
        boundsBehavior: Flickable.StopAtBounds

        TextArea {
            id: previewArea
            width: preview.width - Th.space5
            readOnly: true
            wrapMode: TextArea.NoWrap
            color: Th.text
            font.family: "Consolas"
            font.pixelSize: Th.fontSmall
            selectByMouse: true
            background: Rectangle { color: Th.surface }
        }
    }

    // The page refreshes the text through this function; the pane owns the
    // text area, so the page cannot assign to it directly.
    function refresh(text) {
        previewArea.text = text
    }
}
