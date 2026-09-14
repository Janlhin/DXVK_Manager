import QtQuick
import QtQuick.Controls
import "theme.js" as Th

// Everything that narrows or arranges the library lives behind the one 筛选
// button: status, platform, view and sort. Changes apply immediately, so there
// is no 应用 button - only 重置 and 关闭.
Dialog {
    id: sheet
    objectName: "filterSheet"

    property string dxtkFilter: "all"
    property string platformFilter: ""
    property var platformOptions: []
    property var dxtkCounts: ({"all": 0, "patched": 0, "clean": 0})
    property string viewMode: "grid"
    property string sortKey: "name"
    property bool sortDescending: false

    signal dxtkChosen(string value)
    signal platformChosen(string value)
    signal viewChosen(string mode)
    signal sortChosen(string key)
    signal orderChosen(bool descending)

    modal: true
    anchors.centerIn: parent
    width: Math.min(sheet.parent ? sheet.parent.width - 80 : 560, 560)
    height: body.implicitHeight + 116
    padding: 0

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        color: Th.surface
        radius: Th.radiusPanel
        border.width: 1
        border.color: Th.borderStrong
    }

    // --- small building blocks (same shapes the toolbar used to show) -----
    component Track: Rectangle {
        id: track
        default property alias content: trackRow.data
        implicitWidth: trackRow.implicitWidth + Th.space1
        implicitHeight: trackRow.implicitHeight + Th.space1
        radius: Th.radiusControl
        color: Th.surfaceAlt
        border.width: 1
        border.color: Th.borderSubtle

        Row {
            id: trackRow
            anchors.centerIn: parent
            spacing: 2
        }
    }

    component Pick: Button {
        id: pick
        property bool active: false
        padding: 6
        checkable: true
        checked: active
        background: Rectangle {
            radius: Th.radiusControl - 2
            color: pick.checked ? Th.accentDark
                 : (pick.hovered ? Th.surfaceHover : "transparent")
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        contentItem: Text {
            text: pick.text
            color: pick.checked ? "#ffffff" : Th.textMuted
            font.pixelSize: Th.fontSmall
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    component GroupLabel: Text {
        color: Th.textMuted
        font.pixelSize: Th.fontCaption
    }

    header: Item {
        height: 52

        Text {
            anchors.left: parent.left
            anchors.leftMargin: Th.space5
            anchors.verticalCenter: parent.verticalCenter
            text: "筛选与视图"
            color: Th.text
            font.pixelSize: Th.fontTitle
            font.bold: true
        }
    }

    contentItem: Column {
        id: body
        spacing: Th.space4
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Th.space5

        // --- status ------------------------------------------------------
        Column {
            spacing: Th.space2
            GroupLabel { text: "状态" }
            Track {
                Pick {
                    text: "全部 " + sheet.dxtkCounts.all
                    active: sheet.dxtkFilter === "all"
                    onClicked: sheet.dxtkChosen("all")
                }
                Pick {
                    text: "已装 DXVK " + sheet.dxtkCounts.patched
                    active: sheet.dxtkFilter === "patched"
                    onClicked: sheet.dxtkChosen("patched")
                }
                Pick {
                    text: "未安装 " + sheet.dxtkCounts.clean
                    active: sheet.dxtkFilter === "clean"
                    onClicked: sheet.dxtkChosen("clean")
                }
            }
        }

        // --- platform ----------------------------------------------------
        Column {
            spacing: Th.space2
            visible: sheet.platformOptions.length > 0
            GroupLabel { text: "平台" }
            Track {
                Repeater {
                    model: sheet.platformOptions
                    delegate: Pick {
                        text: modelData.label + " " + modelData.count
                        active: sheet.platformFilter === modelData.value
                        onClicked: sheet.platformChosen(modelData.value)
                    }
                }
            }
        }

        // --- view and sort ----------------------------------------------
        Row {
            spacing: Th.space5

            Column {
                spacing: Th.space2
                GroupLabel { text: "视图" }
                Track {
                    Pick {
                        text: "卡片"
                        active: sheet.viewMode === "grid"
                        onClicked: sheet.viewChosen("grid")
                    }
                    Pick {
                        text: "列表"
                        active: sheet.viewMode === "list"
                        onClicked: sheet.viewChosen("list")
                    }
                }
            }

            Column {
                spacing: Th.space2
                GroupLabel { text: "排序" }
                Column {
                    spacing: 2

                    Track {
                        Pick {
                            text: "名称"
                            active: sheet.sortKey === "name"
                            onClicked: sheet.sortChosen("name")
                        }
                        Pick {
                            text: "平台"
                            active: sheet.sortKey === "platform"
                            onClicked: sheet.sortChosen("platform")
                        }
                        Pick {
                            text: "Direct3D"
                            active: sheet.sortKey === "direct3d"
                            onClicked: sheet.sortChosen("direct3d")
                        }
                    }
                    Track {
                        Pick {
                            text: "架构"
                            active: sheet.sortKey === "arch"
                            onClicked: sheet.sortChosen("arch")
                        }
                        Pick {
                            text: "已装优先"
                            active: sheet.sortKey === "dxtk"
                            onClicked: sheet.sortChosen("dxtk")
                        }
                        Pick {
                            text: sheet.sortDescending ? "↓ 降序" : "↑ 升序"
                            active: false
                            onClicked: sheet.orderChosen(!sheet.sortDescending)
                        }
                    }
                }
            }
        }
    }

    footer: Item {
        height: 48

        Button {
            anchors.left: parent.left
            anchors.leftMargin: Th.space5
            anchors.verticalCenter: parent.verticalCenter
            text: "重置"
            padding: 6
            onClicked: {
                sheet.dxtkChosen("all")
                sheet.platformChosen("")
                sheet.viewChosen("grid")
                sheet.sortChosen("name")
                sheet.orderChosen(false)
            }
            background: Rectangle {
                radius: Th.radiusControl
                color: parent.hovered ? Th.surfaceHover : Th.surfaceAlt
            }
            contentItem: Text {
                text: parent.text
                color: Th.text
                font.pixelSize: Th.fontSmall
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        Button {
            anchors.right: parent.right
            anchors.rightMargin: Th.space5
            anchors.verticalCenter: parent.verticalCenter
            text: "关闭"
            padding: 6
            onClicked: sheet.close()
            background: Rectangle {
                radius: Th.radiusControl
                color: parent.hovered ? Th.primaryHover : Th.primary
            }
            contentItem: Text {
                text: parent.text
                color: Th.primaryText
                font.pixelSize: Th.fontSmall
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
