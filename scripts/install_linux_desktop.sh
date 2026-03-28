#!/usr/bin/env bash
set -euo pipefail

APP_ID="nyini"
APP_NAME="Nyini"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_HOME="${XDG_DATA_HOME}/${APP_ID}"
VENV_DIR="${APP_HOME}/venv"
APPLICATIONS_DIR="${XDG_DATA_HOME}/applications"
ICON_DIR="${XDG_DATA_HOME}/icons/hicolor/512x512/apps"
WRAPPER_PATH="${XDG_BIN_HOME}/${APP_ID}"
DESKTOP_FILE_PATH="${APPLICATIONS_DIR}/${APP_ID}.desktop"
ICON_PATH="${ICON_DIR}/${APP_ID}.png"

mkdir -p "${APP_HOME}" "${XDG_BIN_HOME}" "${APPLICATIONS_DIR}" "${ICON_DIR}"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PYTHON}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  PYTHON_BIN=""
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python introuvable dans le PATH." >&2
  exit 1
fi

BOOTSTRAP_VENV=0
if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  BOOTSTRAP_VENV=1
fi

"${VENV_DIR}/bin/pip" install --upgrade pip
if [[ "${BOOTSTRAP_VENV}" -eq 1 ]] || ! "${VENV_DIR}/bin/pip" show nyini >/dev/null 2>&1; then
  "${VENV_DIR}/bin/pip" install "${REPO_ROOT}"
else
  "${VENV_DIR}/bin/pip" install --no-deps --force-reinstall "${REPO_ROOT}"
fi
install -m 0644 "${REPO_ROOT}/src/assets/icons/nyini.png" "${ICON_PATH}"

cat > "${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "${VENV_DIR}/bin/nyini" "\$@"
EOF
chmod +x "${WRAPPER_PATH}"

cat > "${DESKTOP_FILE_PATH}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
Comment=Desktop wallpaper manager for local Linux libraries
Exec=${WRAPPER_PATH}
Icon=${APP_ID}
Terminal=false
Categories=Graphics;Utility;
Keywords=wallpaper;background;images;
StartupNotify=true
StartupWMClass=${APP_NAME}
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${APPLICATIONS_DIR}" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f "${XDG_DATA_HOME}/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Nyini installe dans le launcher."
echo "Commande: ${WRAPPER_PATH}"
echo "Desktop file: ${DESKTOP_FILE_PATH}"
