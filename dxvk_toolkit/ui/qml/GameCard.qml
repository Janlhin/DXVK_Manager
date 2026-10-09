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
    // Pre-sliced, top-rounded card artwork (§22 scheme B). The grid delegate
    // must pass model.coverCardUrl here; the Image below binds exactly this.
    property string coverCardUrl: ""
    property bool selected: false

    signal activated()
    signal opened()

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
        radius: Th.radiusCard
        color: hover.hovered ? Th.surfaceHover : Th.surfaceRaised
        // 不再常驻 1px 描边：靠表面色区分卡片与背景，只在与交互态出现描边
        border.width: card.selected || hover.hovered ? 1 : 0
        border.color: card.selected ? Th.accent : Th.borderStrong
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
            // Rectangle clip is rectangular and ignores the frame radius, so
            // the artwork's square corners used to poke past the rounded
            // frame. Rounding the artwork itself keeps the corners honest;
            // the pre-sliced PNG's baked corners line up with this radius.
            radius: Th.radiusCard
            clip: true

            Image {
                anchors.fill: parent
                source: card.coverCardUrl
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
                font.pixelSize: Th.fontDisplay
                font.bold: true
                visible: card.coverCardUrl === ""
            }

            // platform chip
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: Th.space2
                radius: Th.radiusMicro
                color: "#b3000000"
                width: platformText.implicitWidth + Th.space3
                height: platformText.implicitHeight + Th.space1
                Text {
                    id: platformText
                    anchors.centerIn: parent
                    text: card.platformLabel
                    color: "#f0f2f5"
                    font.pixelSize: Th.fontMicro
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
                anchors.leftMargin: Th.space2
                anchors.rightMargin: Th.space2
                anchors.topMargin: Th.space2
                anchors.bottomMargin: 0
                text: card.title
                color: hover.hovered ? Th.text : "#d7dbe2"
                font.pixelSize: Th.fontBody
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
                lineHeight: 0.95
                height: 30
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: Th.space2
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Th.space2
                text: card.subtitle
                color: Th.textDim
                font.pixelSize: Th.fontCaption
                elide: Text.ElideRight
                anchors.right: badge.left
                anchors.rightMargin: Th.space2
            }

            // Same badge component as the list and the dialog.
            StatusChip {
                id: badge
                anchors.right: parent.right
                anchors.rightMargin: Th.space2
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Th.space2 - 2
                text: card.statusText
                kind: card.statusKind
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
            onDoubleClicked: card.opened()
        }
    }
}
