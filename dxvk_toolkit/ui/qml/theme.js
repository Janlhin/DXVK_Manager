.pragma library
// Shared palette. Every QML file imports this as: import "theme.js" as Th

var bg = "#141619"
var surface = "#1b1e23"
var surfaceAlt = "#20242b"
var surfaceHover = "#262b34"
var border = "#2c313a"
var borderStrong = "#3a4150"
var text = "#e7e9ec"
var textMuted = "#98a2b3"
var textDim = "#6f7885"
var accent = "#5b8cff"
var accentHover = "#7aa2ff"
var accentDark = "#3c63c9"
var ok = "#3ecf8e"
var warn = "#e2b341"
var error = "#e5686a"

// Filled buttons: a deep blue with light text reads as a button without
// glaring against the dark interface.
var primary = "#33549f"
var primaryHover = "#3f66bd"
var primaryText = "#e6ecfb"

// Corner radius, aligned with the Fluent token scale
// (borderRadiusSmall 2 / Medium 4 / XLarge 8 / 2XLarge 12):
//   control   buttons, inputs, selects, chips   -> 4
//   micro     badges, checkboxes, thumbnails    -> 4
//   card      cards, list containers            -> 8
//   panel     dialogs, big surfaces             -> 12
var radiusControl = 4
var radiusMicro = 4
var radiusCard = 8
var radiusPanel = 12
var radiusHairline = 1

// Older files refer to these names.
var radius = radiusCard
var radiusSmall = radiusControl
var cardWidth = 168
var cardHeight = 252
var cardFooter = 54
// Spacing follows a 4 px base grid: 4 / 8 / 12 / 16 / 24 / 32.
// Every margin, padding and gap in the interface uses one of these.
var space1 = 4
var space2 = 8
var space3 = 12
var space4 = 16
var space5 = 24
var space6 = 32

var gap = 16
var pad = 16

// Type sizes: micro 10, caption 11, body 13, title 15, heading 18.
var fontMicro = 10
var fontCaption = 11
var fontBody = 13
var fontTitle = 15
var fontHeading = 18

function platformColor(platform) {
    switch ((platform || "").toLowerCase()) {
    case "steam": return "#1b6ab8"
    case "epic": return "#2a2a2a"
    case "gog": return "#7b3fa0"
    case "ubisoft": return "#0a63b0"
    case "battlenet": return "#0f6fbf"
    case "riot": return "#c0392b"
    case "wegame": return "#c0392b"
    case "mihoyo": return "#3c6ea5"
    case "ea": return "#c0392b"
    default: return "#3a4150"
    }
}

function statusColor(kind) {
    switch (kind) {
    case "ok": return ok
    case "warn": return warn
    case "error": return error
    default: return textDim
    }
}

function statusBg(kind) {
    switch (kind) {
    case "ok": return "#1d3a2c"
    case "warn": return "#3a3320"
    case "error": return "#3a2426"
    default: return surfaceAlt
    }
}
