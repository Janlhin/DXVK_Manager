import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// A tool tip we control. The built-in ToolTip is drawn by the Qt Quick
// Controls style and ignored the application palette, so it stayed a glaring
// white box in the middle of a dark window.
Popup {
    id: tip
    objectName: "darkTip"

    property string body: ""
    readonly property real maxTipWidth: 520

    padding: 0
    closePolicy: Popup.NoAutoClose
    focus: false
    dim: false
    modal: false

    // Measuring the text against the popup's own implicit size was a binding
    // loop. The text is given a width first; everything else follows from it.
    readonly property real textWidth: Math.min(maxTipWidth,
                                               Math.max(200, tipText.contentWidth + Th.space3))

    contentItem: Text {
        id: tipText
        width: tip.textWidth
        leftPadding: Th.space3
        topPadding: Th.space2
        text: tip.body
        color: Th.text
        font.pixelSize: Th.fontSmall
        lineHeight: Th.lineHeight
        wrapMode: Text.WordWrap
    }

    implicitWidth: tipText.width
    implicitHeight: tipText.height
    width: implicitWidth
    height: implicitHeight

    background: Rectangle {
        color: Th.surfaceAlt
        radius: Th.radiusControl
        border.width: 1
        border.color: Th.borderStrong
    }
}
