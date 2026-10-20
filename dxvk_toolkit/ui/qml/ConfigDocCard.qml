import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// §34 / T21: the sectioned documentation card behind the ⓘ badge. Three
// parts (curated summary / example / raw upstream block), monospace code
// blocks, scrollable and capped at 70% of the window - the long Reflex
// style docs never fit a hover tip. Data comes from the row's doc role,
// which the Python side fills from OptionGroup.doc_parts().
Popup {
    id: docCard
    // Snapshot of the clicked row's fields: the delegate itself can be
    // destroyed by the list while the card is open (it scrolls away), so
    // holding the object reference would crash the bindings.
    property var row: null
    readonly property var doc: row && row.doc ? row.doc : ({})

    function openFor(target) {
        row = {"label": target.label, "optionKey": target.optionKey, "doc": target.doc || {}}
        open()
    }

    modal: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 80, 560)
    height: Math.min(parent.height * 0.7, 620)
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: "#66000000" }
    background: Rectangle {
        radius: Th.radiusCard
        color: Th.surface
        border.width: 1
        border.color: Th.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Th.space4
            Layout.rightMargin: Th.space3
            Layout.topMargin: Th.space3
            spacing: 2

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: docCard.row ? docCard.row.label : ""
                    color: Th.text
                    font.pixelSize: Th.fontTitle
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: "✕"
                    color: docClose.containsMouse ? Th.error : Th.textMuted
                    font.pixelSize: Th.fontBody

                    MouseArea {
                        id: docClose
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: docCard.close()
                    }
                }
            }

            Text {
                text: docCard.row ? docCard.row.optionKey : ""
                color: Th.textMuted
                font.family: "Consolas"
                font.pixelSize: Th.fontCaption
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Th.borderSubtle }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: docBody.implicitHeight + Th.space4 * 2
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: docBody
                x: Th.space5
                y: Th.space4
                width: docCard.width - Th.space5 * 2
                spacing: Th.space3

                ColumnLayout {
                    visible: docCard.doc.summary !== ""
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: qsTr("说明")
                        color: Th.textMuted
                        font.pixelSize: Th.fontCaption
                        font.bold: true
                    }
                    Text {
                        text: docCard.doc.summary || ""
                        color: Th.text
                        font.pixelSize: Th.fontSmall
                        lineHeight: Th.lineHeight
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: qsTr("示例")
                        color: Th.textMuted
                        font.pixelSize: Th.fontCaption
                        font.bold: true
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        // Height from the content: a bare Rectangle would
                        // collapse to 0 and let the TextEdit overlap the
                        // next section.
                        implicitHeight: exampleText.implicitHeight + Th.space2 * 2
                        radius: Th.radiusSmall
                        color: Th.bg
                        border.width: 1
                        border.color: Th.border

                        TextEdit {
                            id: exampleText
                            x: Th.space3
                            y: Th.space2
                            width: parent.width - Th.space5
                            text: docCard.doc.example || ""
                            readOnly: true
                            selectByMouse: true
                            color: Th.accent
                            font.family: "Consolas"
                            font.pixelSize: Th.fontSmall
                            wrapMode: TextEdit.Wrap
                        }
                    }
                }

                ColumnLayout {
                    visible: docCard.doc.original !== ""
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: qsTr("DXVK 原文")
                        color: Th.textMuted
                        font.pixelSize: Th.fontCaption
                        font.bold: true
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: originalText.implicitHeight + Th.space2 * 2
                        radius: Th.radiusSmall
                        color: Th.bg
                        border.width: 1
                        border.color: Th.border

                        TextEdit {
                            id: originalText
                            x: Th.space3
                            y: Th.space2
                            width: parent.width - Th.space5
                            text: docCard.doc.original || ""
                            readOnly: true
                            selectByMouse: true
                            color: Th.text
                            font.family: "Consolas"
                            font.pixelSize: Th.fontSmall
                            wrapMode: TextEdit.Wrap
                        }
                    }
                }
            }
        }
    }
}
