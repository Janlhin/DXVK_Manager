import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// A small, flat button for secondary actions (presets, clear, reset).
// The pages used to define their own copies of this; one shared component
// keeps the padding and the label size consistent across the interface.
Button {
    id: mini
    padding: 6
    opacity: enabled ? 1.0 : 0.45
    background: Rectangle {
        radius: Th.radiusControl
        color: mini.hovered ? Th.surfaceHover : Th.surfaceAlt
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    contentItem: Text {
        text: mini.text
        color: Th.text
        font.pixelSize: Th.fontCaption
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
