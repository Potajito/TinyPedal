#!/bin/bash

#  TinyPedal is an open-source overlay application for racing simulation.
#  Copyright (C) 2022-2026 TinyPedal developers, see contributors.md file
#
#  This file is part of TinyPedal.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Build a portable x86_64 AppImage of TinyPedal.
#
# Bundles a relocatable CPython (python-build-standalone) plus prebuilt
# manylinux wheels, so no compilation happens on the build machine and the
# result runs on any distro with glibc >= 2.28.
#
# Usage: ./build_appimage.sh [--out DIR] [--verify-docker] [--skip-tests] [--keep-workdir]
# Overridable via environment: PBS_RELEASE, PY_VERSION, PYSIDE6_VERSION,
# PSUTIL_VERSION, PYXDG_VERSION, APPIMAGETOOL_URL

set -euo pipefail

# ==== Build components (pinned) ====
PBS_RELEASE="${PBS_RELEASE:-20261009}"
PY_VERSION="${PY_VERSION:-3.11}"
PY_FULL_VERSION="${PY_FULL_VERSION:-3.11.17}"
PYSIDE6_VERSION="${PYSIDE6_VERSION:-6.12.0}"
PSUTIL_VERSION="${PSUTIL_VERSION:-6.1.1}"   # matches requirements.txt
PYXDG_VERSION="${PYXDG_VERSION:-0.28}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage}"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/cpython-${PY_FULL_VERSION}%2B${PBS_RELEASE}-x86_64-unknown-linux-gnu-install_only.tar.gz"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
# Heavy build tree lives outside the repo (repo folders may be file-synced,
# and sync clients can race with or revert the tens of thousands of files
# a python bundle contains). Only the final AppImage is written to dist/.
WORK_DIR="${BUILD_WORKDIR:-${TMPDIR:-/tmp}/tinypedal-appimage-build}"
APP_DIR="${WORK_DIR}/TinyPedal.AppDir"
APP_ROOT="${APP_DIR}/usr/share/TinyPedal"
CACHE_DIR="${WORK_DIR}/cache"

OUT_DIR="${DIST_DIR}"
RUN_TESTS="true"
VERIFY_DOCKER="false"
VERIFY_DOCKER_IMAGE="ubuntu:22.04"
KEEP_WORKDIR="false"

APP_NAME="TinyPedal"
PY_BIN="${PY_VERSION}"

die() { echo "ERROR:$1" >&2; exit 1; }
log() { echo "INFO:$1"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT_DIR="${2:?}"; shift 2;;
        --verify-docker) VERIFY_DOCKER="true"; shift;;
        --verify-docker-image) VERIFY_DOCKER_IMAGE="${2:?}"; shift 2;;
        --skip-tests) RUN_TESTS="false"; shift;;
        --keep-workdir) KEEP_WORKDIR="true"; shift;;
        *) die "unknown option '$1'";;
    esac
done

command -v curl >/dev/null || die "curl not found"
command -v tar >/dev/null || die "tar not found"
command -v ar >/dev/null || die "ar (binutils) not found"

# ==== App version ====
APP_VER="$(grep -w '__version__' "${REPO_ROOT}/tinypedal/version.py" | grep -o -E '[0-9]+\.[0-9]+\.[0-9]+')"
[ -n "${APP_VER}" ] || die "failed to read app version from tinypedal/version.py"
OUTPUT_FILE="${OUT_DIR}/${APP_NAME}-${APP_VER}-x86_64.AppImage"
log "building ${APP_NAME} ${APP_VER} for x86_64"

# ==== Submodules ====
SUBMODULE_PATHS="$(awk -F= '/^\spath/{gsub(/ /,"",$2); print $2}' "${REPO_ROOT}/.gitmodules")"
[ -n "${SUBMODULE_PATHS}" ] || die "invalid or missing .gitmodules"
for REL_PATH in ${SUBMODULE_PATHS}; do
    if [ ! -f "${REPO_ROOT}/${REL_PATH}/__init__.py" ]; then
        log "submodule '${REL_PATH}' missing, initializing"
        git -C "${REPO_ROOT}" submodule update --init --recursive
        break
    fi
done
for REL_PATH in ${SUBMODULE_PATHS}; do
    [ -f "${REPO_ROOT}/${REL_PATH}/__init__.py" ] || die "submodule '${REL_PATH}' not found, run: git submodule update --init --recursive"
done

# Vendored third-party libraries (plain directories, not git submodules)
VENDORED_PATHS="thirdparty/pyAMS2SharedMemory"
for REL_PATH in ${VENDORED_PATHS}; do
    [ -f "${REPO_ROOT}/${REL_PATH}/__init__.py" ] || die "vendored library '${REL_PATH}' not found"
done

rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/usr" "${APP_ROOT}" "${CACHE_DIR}" "${OUT_DIR}"

# ==== Bundled Python (relocatable, glibc 2.17+) ====
PBS_TARBALL="${CACHE_DIR}/cpython-${PY_FULL_VERSION}-${PBS_RELEASE}-install_only.tar.gz"
if [ ! -f "${PBS_TARBALL}" ]; then
    log "downloading portable CPython ${PY_FULL_VERSION}"
    curl -L --fail -o "${PBS_TARBALL}.part" "${PBS_URL}"
    mv "${PBS_TARBALL}.part" "${PBS_TARBALL}"
fi
log "extracting CPython into AppDir"
tar -xzf "${PBS_TARBALL}" -C "${APP_DIR}/usr" --strip-components=1

BUNDLED_PY="${APP_DIR}/usr/bin/python${PY_BIN}"
[ -x "${BUNDLED_PY}" ] || die "bundled python not found at ${BUNDLED_PY}"
"${BUNDLED_PY}" -c 'import sys; assert sys.version_info[:2] >= (3, 11), sys.version' || die "bundled python failed to run"

# ==== Python dependencies (prebuilt manylinux wheels only) ====
log "installing PySide6 Essentials+Addons ${PYSIDE6_VERSION}, psutil ${PSUTIL_VERSION}, pyxdg ${PYXDG_VERSION}"
env -u PYTHONPATH "${BUNDLED_PY}" -m pip install \
    --no-cache-dir --disable-pip-version-check --only-binary=:all: \
    "PySide6-Essentials==${PYSIDE6_VERSION}" \
    "PySide6-Addons==${PYSIDE6_VERSION}" \
    "psutil==${PSUTIL_VERSION}" \
    "pyxdg==${PYXDG_VERSION}" \
    > /dev/null

# Verify QtMultimedia (pace notes sound) is included in the bundle
env -u PYTHONPATH QT_QPA_PLATFORM=offscreen "${BUNDLED_PY}" -c \
    "from PySide6 import QtWidgets, QtMultimedia" \
    || die "PySide6 QtMultimedia is not importable, add PySide6-Addons to the dependency list"

# ==== Copy application files (mirrors install.sh) ====
log "copying application files"
cp "${REPO_ROOT}/run.py" "${REPO_ROOT}/README.md" "${REPO_ROOT}/LICENSE.txt" "${APP_ROOT}/"
cp -r "${REPO_ROOT}/docs" "${APP_ROOT}/docs"
mkdir -p "${APP_ROOT}/images"
cp "${REPO_ROOT}"/images/*.png "${REPO_ROOT}"/images/*.txt "${APP_ROOT}/images/"
cp -r "${REPO_ROOT}/tinypedal" "${APP_ROOT}/tinypedal"
mkdir -p "${APP_ROOT}/thirdparty"
for REL_PATH in ${SUBMODULE_PATHS} ${VENDORED_PATHS}; do
    cp -r "${REPO_ROOT}/${REL_PATH}" "${APP_ROOT}/${REL_PATH}"
done

# Strip caches, VCS metadata, and packaging tools from the bundle
find "${APP_ROOT}" "${APP_DIR}/usr/lib/python${PY_BIN}/site-packages" \
    -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "${APP_ROOT}" -name ".git*" -type f -delete
rm -rf "${APP_DIR}/usr/lib/python${PY_BIN}/site-packages"/{pip,setuptools,wheel,_distutils_hack,distutils-precedence.pth}
rm -rf "${APP_DIR}/usr/lib/python${PY_BIN}"/{test,idlelib,turtle.py,turtledemo,__phello__.foo.py}
rm -rf "${APP_DIR}/usr/share"/{man,doc}

# Prune Qt modules TinyPedal does not use (only QtWidgets + QtMultimedia
# are imported; see tinypedal source). Keep-lists below cover everything
# required for: xcb + wayland platforms, svg icons, printing, and the
# ffmpeg sound backend (QtMultimedia + bundled libav).
PYSIDE_DIR="${APP_DIR}/usr/lib/python${PY_BIN}/site-packages/PySide6"

# Dev/build-time artifacts, QML, translations
rm -rf "${PYSIDE_DIR}"/{doc,include,lib,glue,metatypes,scripts,typesystems} \
    "${PYSIDE_DIR}/Qt"/{qml,translations,libexec}

# Python binding modules: drop everything outside the keep-list
KEEP_MODULES="QtCore QtGui QtWidgets QtNetwork QtDBus QtOpenGL QtOpenGLWidgets QtMultimedia QtMultimediaWidgets QtSvg QtSvgWidgets QtPrintSupport"
for MODULE_FILE in "${PYSIDE_DIR}"/*.abi3.so; do
    MODULE_NAME="$(basename "${MODULE_FILE}" .abi3.so)"
    KEEP=""
    for KEEP_NAME in ${KEEP_MODULES}; do
        [ "${MODULE_NAME}" = "${KEEP_NAME}" ] && KEEP="1" && break
    done
    if [ -z "${KEEP}" ]; then
        rm -f "${MODULE_FILE}" "${PYSIDE_DIR}/${MODULE_NAME}.pyi"
    fi
done

# Qt shared libraries: drop libQt6* outside the keep-list (exact match)
# (all non-Qt6 libs are kept: libicu, ffmpeg libav/libsw, etc.)
# Note: Qt6Qml/Qt6Quick/Qt6Concurrent are required by the ffmpeg multimedia
# plugin and Qt6Multimedia, even though TinyPedal never uses QML itself.
KEEP_LIBS="libQt6Core libQt6Gui libQt6Widgets libQt6Network libQt6DBus libQt6XcbQpa libQt6WaylandClient libQt6WlShellIntegration libQt6OpenGL libQt6OpenGLWidgets libQt6Multimedia libQt6MultimediaWidgets libQt6Svg libQt6SvgWidgets libQt6PrintSupport libQt6FFmpegStub-crypto libQt6FFmpegStub-ssl libQt6FFmpegStub-va libQt6FFmpegStub-va-drm libQt6FFmpegStub-va-x11 libQt6Qml libQt6Quick libQt6Concurrent libQt6QmlModels libQt6QmlMeta libQt6QmlWorkerScript libQt6ShaderTools"
for LIB_FILE in "${PYSIDE_DIR}/Qt/lib"/libQt6*; do
    LIB_NAME="$(basename "${LIB_FILE}")"
    LIB_BASE="${LIB_NAME%%.*}"
    KEEP=""
    for KEEP_NAME in ${KEEP_LIBS}; do
        [ "${LIB_BASE}" = "${KEEP_NAME}" ] && KEEP="1" && break
    done
    [ -z "${KEEP}" ] && rm -f "${LIB_FILE}"
done

# Plugin bundles for removed modules
rm -rf "${PYSIDE_DIR}/Qt/plugins"/{assetimporters,canbus,designer,egldeviceintegrations,generic,geometryloaders,geoservices,position,printsupport,qmltooling,renderers,renderplugins,sceneparsers,scxmldatamodel,sensors,sqldrivers,texttospeech,webview,vectorimageformats}
rm -rf "${PYSIDE_DIR}/Qt/plugins/wayland-graphics-integration-server"
# Orphan plugins inside kept directories (link pruned-away modules)
rm -f "${PYSIDE_DIR}/Qt/plugins/platforms"/libqeglfs*.so \
    "${PYSIDE_DIR}/Qt/plugins/platforminputcontexts"/libqtvirtualkeyboardplugin.so \
    "${PYSIDE_DIR}/Qt/plugins/imageformats"/libqpdf.so

# ==== Self-containment check ====
# A pruned-away Qt dependency would silently resolve from the host system
# libraries (version mismatch = crash or subtle breakage on other distros).
log "checking bundle self-containment (no host Qt/ffmpeg pollution)"
SELF_CONTAIN_OK="1"
while IFS= read -r -d '' SO_FILE; do
    BAD_LINES="$(ldd "${SO_FILE}" 2>/dev/null | grep -E "lib(Qt6|av|sw|icu|shiboken|pyside|python)" | grep -v -F "${APP_DIR}" || true)"
    if [ -n "${BAD_LINES}" ]; then
        echo "NOT SELF-CONTAINED: ${SO_FILE}"
        echo "${BAD_LINES}"
        SELF_CONTAIN_OK="0"
    fi
done < <(find "${PYSIDE_DIR}" "${APP_DIR}/usr/bin" "${APP_DIR}/usr/lib" \
    -maxdepth 4 -type f \( -name "*.so" -o -name "*.so.*" \) -print0)
[ "${SELF_CONTAIN_OK}" = "1" ] || die "bundle pulls Qt/ffmpeg libraries from the host system, extend the keep-lists"

# ==== Launcher, desktop entry, icons ====
cat > "${APP_DIR}/AppRun" << EOF
#!/bin/sh
# TinyPedal AppImage launcher
APPDIR="\$(dirname "\$(readlink -f "\$0")")"
export APPDIR
export PYTHONHOME="\${APPDIR}/usr"
export PYTHONPATH=""
export PYTHONNOUSERSITE=1
export PATH="\${APPDIR}/usr/bin:\${PATH}"
export LD_LIBRARY_PATH="\${APPDIR}/usr/lib\${LD_LIBRARY_PATH:+:\${LD_LIBRARY_PATH}}"
exec "\${APPDIR}/usr/bin/python${PY_BIN}" "\${APPDIR}/usr/share/TinyPedal/run.py" -p 6 "\$@"
EOF
chmod 755 "${APP_DIR}/AppRun"

cat > "${APP_DIR}/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
GenericName=Overlay for Racing Simulator
Comment=Free and open source telemetry overlay application for racing simulation
Exec=${APP_NAME}
Icon=tinypedal
Terminal=false
StartupNotify=true
StartupWMClass=${APP_NAME}
Categories=Game;
Keywords=tiny;tinypedal;overlay;rfactor2;lmu;acc;
X-AppImage-Version=${APP_VER}
EOF

cp "${APP_ROOT}/images/icon.png" "${APP_DIR}/tinypedal.png"
ln -sf "tinypedal.png" "${APP_DIR}/.DirIcon"
mkdir -p "${APP_DIR}/usr/share/icons/hicolor/256x256/apps"
cp "${APP_ROOT}/images/icon.png" "${APP_DIR}/usr/share/icons/hicolor/256x256/apps/tinypedal.png"

# Verify the ffmpeg multimedia backend plugin survived pruning
test -f "${PYSIDE_DIR}/Qt/plugins/multimedia/libffmpegmediaplugin.so" \
    || die "ffmpeg multimedia backend plugin missing after prune"

# ==== X11 helper libraries (xcb-util family + xkbcommon pair) ====
# The Qt xcb platform plugin requires the xcb-util family and
# libxkbcommon-x11, which older LTS distros (Ubuntu 22.04, RHEL 8/9) do not
# install by default. Bundle jammy-era builds (glibc 2.14 floor or lower)
# so the AppImage starts there.
# libxkbcommon + libxkbcommon-x11 MUST come from the same release as a
# matched pair: a jammy libxkbcommon-x11 against a newer host libxkbcommon
# (e.g. Fedora) segfaults in xkb_state_update_mask. Bundling both preempts
# the host's versions and keeps the pair consistent.
# Base libxcb/libX11 remain host-provided: every system able to run X11
# apps has them.
log "bundling X11 xcb-util helper libraries"
XCB_HELPER_DEBS="
http://archive.ubuntu.com/ubuntu/pool/universe/x/xcb-util-cursor/libxcb-cursor0_0.1.1-4ubuntu1_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/x/xcb-util-renderutil/libxcb-render-util0_0.3.9-1build1_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/x/xcb-util-image/libxcb-image0_0.4.0-1build1_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/x/xcb-util/libxcb-util1_0.4.0-1build2_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/x/xcb-util-keysyms/libxcb-keysyms1_0.4.0-1build1_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/x/xcb-util-wm/libxcb-icccm4_0.4.1-1.1build2_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/libx/libxkbcommon/libxkbcommon-x11-0_1.4.0-1_amd64.deb
http://archive.ubuntu.com/ubuntu/pool/main/libx/libxkbcommon/libxkbcommon0_1.4.0-1_amd64.deb
"
for DEB_URL in ${XCB_HELPER_DEBS}; do
    DEB_FILE="${CACHE_DIR}/$(basename "${DEB_URL}")"
    if [ ! -f "${DEB_FILE}" ]; then
        curl -fL --max-time 60 -o "${DEB_FILE}.part" "${DEB_URL}"
        mv "${DEB_FILE}.part" "${DEB_FILE}"
    fi
    EXTRACT_DIR="${WORK_DIR}/deb-extract"
    rm -rf "${EXTRACT_DIR}" && mkdir "${EXTRACT_DIR}"
    (
        cd "${EXTRACT_DIR}" \
        && ar x "${DEB_FILE}" \
        && { tar -xf data.tar.zst 2>/dev/null || tar -xf data.tar.xz 2>/dev/null || tar -xf data.tar.gz; } \
        && find . -name "lib*.so.*" -path "*x86_64*" -exec cp -L {} "${APP_DIR}/usr/lib/" \;
    ) || die "failed to extract helper library from $(basename "${DEB_URL}")"
done
rm -rf "${WORK_DIR}/deb-extract"
test -f "${APP_DIR}/usr/lib/libxcb-cursor.so.0" || die "libxcb-cursor.so.0 missing from bundle"
test -f "${APP_DIR}/usr/lib/libxkbcommon.so.0" || die "libxkbcommon.so.0 missing from bundle"

# ==== Smoke tests ====
if [ "${RUN_TESTS}" = "true" ]; then
    log "smoke test: module imports"
    IMPORT_LOG="${CACHE_DIR}/import_test.log"
    (cd "${APP_ROOT}" && env -u PYTHONPATH QT_QPA_PLATFORM=offscreen "${BUNDLED_PY}" -c "
import tinypedal
from tinypedal.constant import APP
from PySide6 import QtWidgets
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import psutil, xdg
app = QtWidgets.QApplication([])
player = QMediaPlayer()
audio = QAudioOutput()
print('tinypedal bundle OK:', APP.VERSION)
") > "${IMPORT_LOG}" 2>&1 || { cat "${IMPORT_LOG}"; die "smoke test failed"; }
    cat "${IMPORT_LOG}"
    grep -q "No QtMultimedia backends" "${IMPORT_LOG}" \
        && die "QtMultimedia ffmpeg backend did not load"

    log "smoke test: headless GUI start (killed by timeout if alive)"
    # -s 0 (multi-instance mode) bypasses the pid-file single-instance check,
    # so the test works even when TinyPedal is running or a stale pid file exists
    set +e
    TIMEOUT_RC=0
    (cd "${WORK_DIR}" && env QT_QPA_PLATFORM=offscreen timeout 12 "${APP_DIR}/AppRun" -s 0 -l 1 > "${CACHE_DIR}/gui_test.log" 2>&1)
    TIMEOUT_RC=$?
    set -e
    if [ "${TIMEOUT_RC}" -ne 124 ]; then
        echo "---- GUI test output ----"
        cat "${CACHE_DIR}/gui_test.log"
        die "GUI smoke test exited unexpectedly (rc=${TIMEOUT_RC})"
    fi
    if grep -q "Traceback" "${CACHE_DIR}/gui_test.log"; then
        echo "---- GUI test output ----"
        cat "${CACHE_DIR}/gui_test.log"
        die "GUI smoke test hit a traceback"
    fi
    log "GUI ran for 12s headless without crashing"
fi

# ==== Portability check in an older-glibc container (optional) ====
if [ "${VERIFY_DOCKER}" = "true" ]; then
    command -v docker >/dev/null || die "docker not found"
    log "verifying AppDir inside ${VERIFY_DOCKER_IMAGE} (older glibc, real X11 via Xvfb)"
    set +e
    (cd "${WORK_DIR}" && docker run --rm -v "${APP_DIR}:/opt/TinyPedal.AppDir:ro" "${VERIFY_DOCKER_IMAGE}" \
        bash -c '
            export DEBIAN_FRONTEND=noninteractive
            # Base X11/GL stack only: deliberately omits the xcb-util family
            # and libxkbcommon-x11, which must come from the bundled helpers
            apt-get update -qq && apt-get install -qq -y --no-install-recommends \
                libglib2.0-0 libfontconfig1 libxkbcommon0 libdbus-1-3 libegl1 libgl1 libpulse0 \
                libxcb1 libxcb-render0 libxcb-shm0 libxcb-xfixes0 libxcb-shape0 libxcb-randr0 \
                libxcb-sync1 libxcb-xkb1 xvfb > /dev/null
            Xvfb :99 -screen 0 1280x800x24 > /dev/null 2>&1 &
            XVFB_PID=$!
            sleep 1
            DISPLAY=:99 timeout 12 /opt/TinyPedal.AppDir/AppRun -s 0 -l 1
            APP_RC=$?
            kill "${XVFB_PID}" 2>/dev/null || true
            exit "${APP_RC}"
        ')
    DOCKER_RC=$?
    set -e
    if [ "${DOCKER_RC}" -ne 124 ]; then
        die "container verification exited with rc=${DOCKER_RC} (expected 124 = still running)"
    fi
    log "runs on ${VERIFY_DOCKER_IMAGE} (glibc $(docker run --rm "${VERIFY_DOCKER_IMAGE}" ldd --version | head -1 | grep -o -E "[0-9]+\.[0-9]+$")) with bundled xcb helpers"
fi

# ==== Pack AppImage ====
log "downloading appimagetool"
APPIMAGETOOL_BIN="${CACHE_DIR}/appimagetool-x86_64.AppImage"
if [ ! -f "${APPIMAGETOOL_BIN}" ]; then
    curl -L --fail -o "${APPIMAGETOOL_BIN}.part" "${APPIMAGETOOL_URL}"
    mv "${APPIMAGETOOL_BIN}.part" "${APPIMAGETOOL_BIN}"
    chmod 755 "${APPIMAGETOOL_BIN}"
fi

log "packing AppImage"
PACK_RC=0
(cd "${WORK_DIR}" && APPIMAGE_EXTRACT_AND_RUN=1 NO_STRIP=true ARCH=x86_64 \
    "${APPIMAGETOOL_BIN}" --comp zstd "${APP_DIR}" "${OUTPUT_FILE}") || PACK_RC=$?
if [ "${PACK_RC}" -ne 0 ]; then
    log "zstd compression unavailable, falling back to default gzip"
    (cd "${WORK_DIR}" && APPIMAGE_EXTRACT_AND_RUN=1 NO_STRIP=true ARCH=x86_64 \
        "${APPIMAGETOOL_BIN}" "${APP_DIR}" "${OUTPUT_FILE}") || die "appimagetool failed (rc=${PACK_RC})"
fi

if [ "${KEEP_WORKDIR}" = "false" ]; then
    rm -rf "${APP_DIR}"
fi

echo
log "done: ${OUTPUT_FILE}"
log "size: $(du -h "${OUTPUT_FILE}" | cut -f1)"
(cd "${OUT_DIR}" && sha256sum "$(basename "${OUTPUT_FILE}")")
