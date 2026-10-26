#!/usr/bin/env bash
# Install the Atlas hardware tools on the car's Jetson (rev B: Orin Nano Super dev kit, JetPack 6,
# Ubuntu 22.04).
#   sudo software/jetson/system/install.sh
# Safe to run again: it replaces the tools and units and keeps /etc/atlas/atlas.conf.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$HERE")"
USER_NAME="${SUDO_USER:-}"
WARN=()

echo ">> packages (libgpiod for the J12 lines)"
PKGS="python3 gpiod python3-libgpiod i2c-tools"
apt-get install -y $PKGS >/dev/null || { apt-get update && apt-get install -y $PKGS >/dev/null; }

echo ">> atlas command in /opt/atlas"
install -d /opt/atlas
rm -rf /opt/atlas/atlas_hw
cp -r "$SRC/atlas_hw" /opt/atlas/
find /opt/atlas -name __pycache__ -prune -exec rm -rf {} +
# Compile now: the shutdown hook runs with the root file system read-only
python3 -m compileall -q /opt/atlas/atlas_hw || true
cat > /usr/local/bin/atlas <<'WRAP'
#!/bin/sh
PYTHONPATH="/opt/atlas${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m atlas_hw.cli "$@"
WRAP
chmod 755 /usr/local/bin/atlas

echo ">> groups and device names (/dev/atlas_vesc, /dev/atlas_supervisor, lidar0)"
groupadd -f i2c
groupadd -f gpio
if [ -n "$USER_NAME" ]; then usermod -aG i2c,dialout,gpio "$USER_NAME"; fi
install -m 644 "$HERE/99-atlas.rules" /etc/udev/rules.d/99-atlas.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty --subsystem-match=i2c-dev || true

echo ">> settings"
install -d /etc/atlas
if [ -f /etc/atlas/atlas.conf ]; then
    # rev A keys that no longer mean anything
    sed -i -e '/^ATLAS_PD_LOWREGION=/d' -e '/^ATLAS_POWER_EN_FIXED=/d' /etc/atlas/atlas.conf
    grep -q '^ATLAS_SUPERVISOR_TTY=' /etc/atlas/atlas.conf || echo 'ATLAS_SUPERVISOR_TTY=/dev/atlas_supervisor' >> /etc/atlas/atlas.conf
else
    install -m 644 "$HERE/atlas.conf" /etc/atlas/atlas.conf
fi
install -d /var/lib/atlas

echo ">> network (lidar: 192.168.0.100/24 on the USB adapter; camera: link-local, MTU 9000)"
for f in "$HERE"/NetworkManager/*.nmconnection; do
    install -m 600 "$f" /etc/NetworkManager/system-connections/
done
nmcli connection reload || true

echo ">> power key: shut down (takes effect after a reboot)"
install -d /etc/systemd/logind.conf.d
install -m 644 "$HERE/logind/90-atlas-power-key.conf" /etc/systemd/logind.conf.d/

echo ">> shutdown hook: HALT / REBOOT to the supervisor at the end of every shutdown"
install -d /usr/lib/systemd/system-shutdown
install -m 755 "$HERE/system-shutdown/atlas-halt" /usr/lib/systemd/system-shutdown/atlas-halt

echo ">> services"
install -m 644 "$HERE"/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable atlas-battery.service atlas-hw-init.service

echo ">> UART1 (serial@3100000, normally /dev/ttyTHS1) must be free for the VESC"
VESC_TTY=""
for t in /sys/class/tty/ttyTHS*; do
    [ -e "$t/device" ] || continue
    case "$(readlink -f "$t/device")" in *3100000.serial*) VESC_TTY="$(basename "$t")" ;; esac
done
if [ -z "$VESC_TTY" ]; then
    WARN+=("no tty on serial@3100000 found: check \`ls -l /sys/class/tty/ttyTHS*/device\` and the udev rule for /dev/atlas_vesc")
else
    echo "   UART1 is /dev/$VESC_TTY"
    unit="serial-getty@$VESC_TTY.service"
    if systemctl is-enabled --quiet "$unit" 2>/dev/null || systemctl is-active --quiet "$unit" 2>/dev/null; then
        systemctl disable --now "$unit" || true
        echo "   disabled $unit (a login prompt on the VESC's UART)"
    fi
    if grep -Eq "console=$VESC_TTY" /proc/cmdline; then
        WARN+=("the kernel console is on $VESC_TTY (/proc/cmdline): remove console=$VESC_TTY from /boot/extlinux/extlinux.conf")
    fi
fi

echo ">> power mode: 25 W (the DC jack is fed from the pack; MAXN_SUPER can exceed its 3.5 A at 12 V)"
if command -v nvpmodel >/dev/null && [ -f /etc/nvpmodel.conf ]; then
    ID="$(sed -n 's/.*POWER_MODEL ID=\([0-9]*\) NAME=25W.*/\1/p' /etc/nvpmodel.conf | head -1)"
    if [ -n "$ID" ]; then
        echo no | nvpmodel -m "$ID" >/dev/null 2>&1 || true
        echo "   nvpmodel -m $ID ($(nvpmodel -q 2>/dev/null | head -1))"
    else
        WARN+=("no 25W mode in /etc/nvpmodel.conf: set the power mode by hand (sudo nvpmodel -q --verbose)")
    fi
else
    WARN+=("nvpmodel not found: set the 25 W power mode by hand")
fi

cat <<MSG

Installed. Reboot, then check with:  atlas status
- Log out and back in (or reboot) for the i2c, gpio and dialout groups to apply to ${USER_NAME:-your user}.
- The supervisor firmware goes on the Pico separately: firmware/supervisor/README.md.
- Check the J12 GPIO line numbers once with \`gpioinfo\` (docs/SOFTWARE.md, rev B).
MSG
for w in "${WARN[@]+"${WARN[@]}"}"; do echo "WARNING: $w"; done
