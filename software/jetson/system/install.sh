#!/usr/bin/env bash
# Install the Atlas hardware tools on the car's Jetson (JetPack 6, Ubuntu 22.04).
#   sudo software/jetson/system/install.sh
# Safe to run again: it replaces the tools and units, keeps /etc/atlas/atlas.conf and the PD files.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$HERE")"
USER_NAME="${SUDO_USER:-}"

echo ">> packages"
apt-get install -y python3-pip i2c-tools >/dev/null || { apt-get update && apt-get install -y python3-pip i2c-tools >/dev/null; }
python3 -c 'import smbus2' 2>/dev/null || pip3 install smbus2

echo ">> atlas command in /opt/atlas"
install -d /opt/atlas
rm -rf /opt/atlas/atlas_hw
cp -r "$SRC/atlas_hw" /opt/atlas/
find /opt/atlas -name __pycache__ -prune -exec rm -rf {} +
cat > /usr/local/bin/atlas <<'WRAP'
#!/bin/sh
PYTHONPATH="/opt/atlas${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m atlas_hw.cli "$@"
WRAP
chmod 755 /usr/local/bin/atlas

echo ">> groups and device permissions"
groupadd -f i2c
if [ -n "$USER_NAME" ]; then usermod -aG i2c,dialout "$USER_NAME"; fi
install -m 644 "$HERE/99-atlas.rules" /etc/udev/rules.d/99-atlas.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=i2c-dev --subsystem-match=tty

echo ">> settings"
install -d /etc/atlas
[ -f /etc/atlas/atlas.conf ] || install -m 644 "$HERE/atlas.conf" /etc/atlas/atlas.conf
install -d /var/lib/atlas

echo ">> network (lidar: 192.168.0.100/24 on the LAN7800; camera: link-local, MTU 9000)"
for f in "$HERE"/NetworkManager/*.nmconnection; do
    install -m 600 "$f" /etc/NetworkManager/system-connections/
done
nmcli connection reload || true

echo ">> power key: shut down (takes effect after a reboot)"
install -d /etc/systemd/logind.conf.d
install -m 644 "$HERE/logind/90-atlas-power-key.conf" /etc/systemd/logind.conf.d/

echo ">> services"
install -m 644 "$HERE"/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable atlas-hw-init.service atlas-battery.service

cat <<MSG

Installed. Reboot, then check with:  atlas status
- Log out and back in (or reboot) for the i2c and dialout groups to apply to ${USER_NAME:-your user}.
- USB-C charging needs the PD controller's configuration: see docs/FLASHING.md, step 4.
  Put the Low Region binary at /etc/atlas/tps25751_lowregion.bin so a blank EEPROM is covered at boot.
MSG
