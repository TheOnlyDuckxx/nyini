#!/usr/bin/env bash
set -euo pipefail

APP_ID="nyini"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_HOME="${XDG_DATA_HOME}/${APP_ID}"
APPLICATIONS_DIR="${XDG_DATA_HOME}/applications"
ICON_DIR="${XDG_DATA_HOME}/icons/hicolor/512x512/apps"

rm -f "${XDG_BIN_HOME}/${APP_ID}"
rm -f "${APPLICATIONS_DIR}/${APP_ID}.desktop"
rm -f "${ICON_DIR}/${APP_ID}.png"
rm -rf "${APP_HOME}"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${APPLICATIONS_DIR}" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f "${XDG_DATA_HOME}/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Nyini desinstalle."
