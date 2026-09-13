import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// A tool tip we control. The built-in ToolTip is drawn by the Qt Quick
// Controls style and ignored the application palette, so it stayed a glaring
// white box in the middle of a dark window.
//
// The opaque surface is the contentItem itself rather than Popup.background:
// the background rectangle was never stretched to the popup, so the page text
// showed straight through the tip.
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

    contentItem: Rectangle {
        id: tipBox
        color: Th.surfaceAlt
        radius: Th.radiusControl
        border.width: 1
        border.color: Th.borderStrong

        // The text is measured unwrapped, then clamped: assigning a width does
        // not feed back into implicitWidth, so there is no binding loop.
        readonly property real lineWidth: Math.min(tip.maxTipWidth,
                                                   Math.max(220, tipText.implicitWidth))

        implicitWidth: lineWidth + Th.space5
        implicitHeight: tipText.implicitHeight + Th.space3

        Text {
            id: tipText
            x: Th.space3
            y: Th.space2
            width: tipBox.lineWidth
            text: tip.body
            color: Th.text
            font.pixelSize: Th.fontSmall
            lineHeight: Th.lineHeight
            wrapMode: Text.WordWrap
        }
    }
}
