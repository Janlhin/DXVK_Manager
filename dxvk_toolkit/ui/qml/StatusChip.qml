import QtQuick
import "theme.js" as Th

// One status badge, shared by the card wall, the list rows and the game dialog
// so the same state never looks like three different things.
Rectangle {
    id: chip
    objectName: "statusChip"

    property string text: ""
    property string kind: "muted"      // ok | warn | error | muted
    // The list needs every badge to be the same width so the column lines up.
    property bool fixedWidth: false

    implicitWidth: fixedWidth ? 96 : label.implicitWidth + Th.space3
    implicitHeight: label.implicitHeight + Th.space2
    radius: Th.radiusControl
    color: Th.statusBg(kind)
    border.width: 1
    border.color: kind === "ok" ? Th.ok
                : kind === "warn" ? Th.warn
                : kind === "error" ? Th.error
                : Th.borderStrong

    // x/y rather than anchors: centring a label whose implicit width defines
    // the parent's width is a binding loop, and Qt breaks it (the chip then
    // collapses to nothing).
    Text {
        id: label
        x: (chip.width - width) / 2
        y: (chip.height - height) / 2
        text: chip.text
        color: chip.kind === "muted" ? Th.textMuted : Th.statusColor(chip.kind)
        font.pixelSize: Th.fontCaption
    }
}
