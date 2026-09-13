.pragma library
// Palette and scales, taken from GitHub's Primer dark theme - the same values
// the reference report page uses:
//   --bg #0d1117  --card #161b22  --border #30363d
//   --text #c9d1d9  --text-muted #8b949e  --accent #58a6ff
//   status: #3fb950 ok / #d29922 warn / #f85149 error
// Type follows that page as well: a comfortable base size with generous
// leading, instead of the cramped 12 px the interface started with.

var bg = "#0d1117"
var surface = "#161b22"
var surfaceAlt = "#1c2128"
var surfaceHover = "#21262d"
var surfaceRaised = "#161b22"
var border = "#30363d"
var borderSubtle = "#21262d"
var borderStrong = "#484f58"
var text = "#e6edf3"
var textMuted = "#8b949e"
var textDim = "#6e7681"
var accent = "#58a6ff"
var accentHover = "#79c0ff"
var accentDark = "#1f6feb"
var ok = "#3fb950"
var warn = "#d29922"
var error = "#f85149"
var gold = "#d29922"

// Filled buttons: a solid accent with dark text is unreadable at this size,
// so primary actions use the accent colour itself with white text.
var primary = "#1f6feb"
var primaryHover = "#388bfd"
var primaryText = "#ffffff"

// 4 px spacing grid.
var space1 = 4
var space2 = 8
var space3 = 12
var space4 = 16
var space5 = 24
var space6 = 32

// Corner radius: controls 6, badges 6, cards 10, dialogs 12.
var radiusControl = 6
var radiusMicro = 6
var radiusCard = 10
var radiusPanel = 12
var radiusHairline = 1

var radius = radiusCard
var radiusSmall = radiusControl

// Type scale: body 15, list rows 14, captions 12-13, headings 17-20.
var fontMicro = 11
var fontCaption = 12
var fontSmall = 13
var fontBody = 15
var fontSubtitle = 14
var fontTitle = 17
var fontHeading = 20
var fontDisplay = 40

var lineHeight = 1.5

var gap = 16
var pad = 16
var cardWidth = 168
var cardHeight = 252
var cardFooter = 62

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
    case "ok": return "rgba(63,185,80,0.15)"
    case "warn": return "rgba(210,153,34,0.15)"
    case "error": return "rgba(248,81,73,0.15)"
    default: return surfaceAlt
    }
}
