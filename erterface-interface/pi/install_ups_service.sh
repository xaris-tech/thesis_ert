#!/usr/bin/env bash
# Install the flat-battery poweroff service (ADR-0085). Run: sudo pi/install_ups_service.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"

raspi-config nonint do_i2c 0 || true              # enable I2C
python3 -c "import smbus2" 2>/dev/null || python3 -c "import smbus" 2>/dev/null \
    || apt-get install -y python3-smbus
if ! i2cdetect -y 1 0x2d 0x2d 2>/dev/null | grep -q 2d; then
    echo "Warning: no UPS HAT (E) at I2C 0x2d yet (reboot after enabling I2C?)." >&2
fi

sed "s|@ERTERFACE_DIR@|$DIR|" "$DIR/pi/erterface-ups.service" \
    > /etc/systemd/system/erterface-ups.service
systemctl daemon-reload
systemctl enable --now erterface-ups.service
systemctl --no-pager status erterface-ups.service | head -5
echo "Logs: journalctl -u erterface-ups -f"
