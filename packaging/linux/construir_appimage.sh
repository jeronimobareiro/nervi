#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Arma el AppImage a partir de la carpeta de PyInstaller.
# Uso: packaging/linux/construir_appimage.sh <dist/Nervi> <iconos> <appimagetool> <salida.AppImage>
set -eu
DIST="$1"; ICONOS="$2"; HERRAMIENTA="$3"; SALIDA="$4"
AQUI="$(dirname "$(readlink -f "$0")")"
APPDIR="$(mktemp -d)/Nervi.AppDir"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/mime/packages" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "$DIST" "$APPDIR/usr/lib/nervi"
cp "$AQUI/AppRun" "$APPDIR/AppRun"
cp "$AQUI/nervi.desktop" "$APPDIR/nervi.desktop"
cp "$AQUI/nervi.desktop" "$APPDIR/usr/share/applications/nervi.desktop"
cp "$AQUI/nervi.xml" "$APPDIR/usr/share/mime/packages/nervi.xml"
cp "$ICONOS/nervi.png" "$APPDIR/nervi.png"
cp "$ICONOS/nervi.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nervi.png"
ln -s nervi.png "$APPDIR/.DirIcon"
ARCH=x86_64 "$HERRAMIENTA" --appimage-extract-and-run "$APPDIR" "$SALIDA"
