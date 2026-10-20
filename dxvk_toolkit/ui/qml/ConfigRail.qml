import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Th

// The category rail (left column): the sections with their counts. The
// counts follow the search text and the difficulty mode, and clicking a
// category filters the option list to it.
//
// The keys are the raw purpose/section names, so the rail does not depend
// on the interface language; the labels come from the model.
Rectangle {
    id: rail

    property string currentSection: ""

    signal sectionSelected(string section)

    width: 148
    color: Th.surface

    Text {
        id: railTitle
        anchors.left: parent.left
        anchors.leftMargin: Th.space3
        anchors.top: parent.top
        anchors.topMargin: Th.space3
        text: qsTr("分类")
        color: Th.textMuted
        font.pixelSize: Th.fontCaption
        font.bold: true
    }

    Item {
        id: railAll
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: railTitle.bottom
        anchors.topMargin: Th.space2
        height: 30

        Rectangle {
            anchors.fill: parent
            anchors.margins: Th.space1
            radius: Th.radiusSmall
            color: rail.currentSection === "" ? Th.accentDark
                   : (railAllHover.containsMouse ? Th.surfaceHover : "transparent")
        }
        MouseArea {
            id: railAllHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: rail.sectionSelected("")
        }
        Text {
            x: Th.space2
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("全部")
            color: rail.currentSection === "" ? "#ffffff" : Th.text
            font.pixelSize: Th.fontSmall
            font.bold: rail.currentSection === ""
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: Th.space3
            anchors.verticalCenter: parent.verticalCenter
            text: configModel.optionCount
            color: rail.currentSection === "" ? "#d7e3f8" : Th.textMuted
            font.pixelSize: Th.fontCaption
        }
    }

    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: railAll.bottom

        Repeater {
            model: configModel.sectionStats

            delegate: Item {
                id: railItem
                required property var modelData
                width: parent.width
                height: 30

                readonly property bool active: rail.currentSection === modelData.key

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: Th.space1
                    radius: Th.radiusSmall
                    color: railItem.active ? Th.accentDark
                           : (railHover.containsMouse ? Th.surfaceHover : "transparent")
                }
                MouseArea {
                    id: railHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        rail.currentSection = railItem.active ? "" : railItem.modelData.key
                        rail.sectionSelected(rail.currentSection)
                    }
                }
                Text {
                    x: Th.space2
                    width: parent.width - Th.space4 - 36
                    anchors.verticalCenter: parent.verticalCenter
                    text: railItem.modelData.label
                    color: railItem.active ? "#ffffff" : Th.text
                    font.pixelSize: Th.fontSmall
                    font.bold: railItem.active
                    elide: Text.ElideRight
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: Th.space3
                    anchors.verticalCenter: parent.verticalCenter
                    text: railItem.modelData.count
                    color: railItem.active ? "#d7e3f8" : Th.textMuted
                    font.pixelSize: Th.fontCaption
                }
            }
        }
    }
}
