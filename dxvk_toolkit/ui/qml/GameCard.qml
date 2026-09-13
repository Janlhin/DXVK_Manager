import QtQuick
import "theme.js" as Th

// One cover card: artwork, title, and a status badge. Cover art is requested
// only when the card is actually created (GridView only builds visible ones).
Item {
    id: card

    property string gameKey: ""
    property string title: ""
    property string platform: ""
    property string platformLabel: ""
    property string subtitle: ""
    property string statusText: ""
    property string statusKind: "muted"
    property string coverUrl: ""
    property bool selected: false

    signal activated()

    width: Th.cardWidth
    height: Th.cardHeight + Th.cardFooter

    // Animating the delegate root stopped the view from creating delegates at
    // all (the same thing a Timer here did), so the motion lives on the inner
    // rectangle: the view only ever sees a static root item.

    function initials(text) {
        var parts = (text || "").split(" ")
        var out = ""
        for (var i = 0; i < parts.length && out.length < 3; i++) {
            if (parts[i].length > 0)
                out += parts[i][0].toUpperCase()
        }
        return out.length > 0 ? out : "?"
    }

    // Model roles are injected after Component.onCompleted, and the change
    // signal is not delivered for that initial assignment either. A binding
    // (here: the timer's running state) is re-evaluated whenever a dependency
    // changes, which is the reliable hook.
    // Nothing is triggered from inside the card: the view reports which
    // cards are visible (see GamesPage.requestVisible) and the bridge loads
    // those. Model roles are injected without a usable change notification,
    // and a Timer here stopped the view from creating delegates at all.

    Rectangle {
        id: frame
        anchors.fill: parent
        radius: Th.radius
        color: hover.hovered ? Th.surfaceHover : Th.surface
        border.width: card.selected ? 2 : 1
        border.color: card.selected ? Th.accent
                                   : (hover.hovered ? Th.borderStrong : Th.border)
        clip: true
        transformOrigin: Item.Center
        scale: hover.hovered ? 1.035 : 1.0

        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on border.color { ColorAnimation { duration: 120 } }
        Behavior on scale {
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }

        // --- artwork -----------------------------------------------------
        Rectangle {
            id: art
            width: parent.width
            height: Th.cardHeight
            color: Th.platformColor(card.platform)
            clip: true

            Image {
                anchors.fill: parent
                source: card.coverUrl
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: Math.round(Th.cardWidth * 2)
                sourceSize.height: Math.round(Th.cardHeight * 2)
                smooth: true
                visible: status === Image.Ready
            }

            Text {
                anchors.centerIn: parent
                text: card.initials(card.title)
                color: "#e7e9ec"
                font.pixelSize: 40
                font.bold: true
                visible: card.coverUrl === ""
            }

            // platform chip
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 8
                radius: Th.radiusMicro
                color: "#cc000000"
                width: platformText.implicitWidth + 12
                height: platformText.implicitHeight + 6
                Text {
                    id: platformText
                    anchors.centerIn: parent
                    text: card.platformLabel
                    color: "#e7e9ec"
                    font.pixelSize: 10
                }
            }
        }

        // --- footer ------------------------------------------------------
        Item {
            anchors.top: art.bottom
            width: parent.width
            height: Th.cardFooter

            Text {
                id: titleText
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 8
                anchors.bottomMargin: 0
                text: card.title
                color: Th.text
                font.pixelSize: 12
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
                lineHeight: 0.95
                height: 30
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                text: card.subtitle
                color: Th.textDim
                font.pixelSize: 10
                elide: Text.ElideRight
                width: parent.width - badge.width - 26
            }

            Rectangle {
                id: badge
                anchors.right: parent.right
                anchors.rightMargin: 8
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                radius: Th.radiusMicro
                color: Th.statusBg(card.statusKind)
                width: badgeText.implicitWidth + 12
                height: badgeText.implicitHeight + 5
                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: card.statusText
                    color: Th.statusColor(card.statusKind)
                    font.pixelSize: 10
                }
            }
        }

        MouseArea {
            id: hover
            anchors.fill: parent
            hoverEnabled: true
            property bool hovered: false
            onEntered: hovered = true
            onExited: hovered = false
            onClicked: card.activated()
            onDoubleClicked: card.activated()
        }
    }
}
