.pragma library
// Shared palette. QML files import this as "theme.js" and use Th.bg etc.

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

var radius = 12
var radiusSmall = 8
var cardWidth = 168
var cardHeight = 252
var cardFooter = 52
var gap = 14
var pad = 18

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
