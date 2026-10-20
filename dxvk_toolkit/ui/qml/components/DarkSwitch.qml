import QtQuick
import QtQuick.Controls
import "../theme.js" as Th

// The pill switch used by the settings page and the configuration page.
//
// It used to be written twice - once as an inline `component DarkSwitch`
// in each page - and the two copies had drifted apart: the configuration
// page's variant lacked the note about the Basic style's implicitWidth.
//
// Basic style 的 implicitWidth 公式只算 background/contentItem，不含
// indicator：contentItem 置空后控件塌缩到 padding*2 = 12px，40px 轨道
// 向右溢出、窄窗口下被窗口边裁掉。将控件钉死为轨道尺寸并归零 padding，
// 让 anchors.right 的语义落在轨道右缘上。
Switch {
    id: sw
    implicitWidth: 40
    implicitHeight: 24
    padding: 0

    indicator: Rectangle {
        implicitWidth: 40
        implicitHeight: 22
        x: 0
        y: (sw.height - height) / 2
        radius: 11
        color: sw.checked ? Th.accentDark : Th.surfaceAlt
        border.width: 1
        border.color: sw.checked ? Th.accent : Th.border

        Behavior on color { ColorAnimation { duration: 120 } }

        Rectangle {
            width: 16
            height: 16
            radius: 8
            y: 2
            x: sw.checked ? parent.width - width - 3 : 3
            color: sw.checked ? "#ffffff" : Th.textMuted
            Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Item {}
}
