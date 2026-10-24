"""USB0 of the Jetson module goes through the stack to the drive board's hub (port 1) and, with the
FLASH switch set, straight to the USB-C socket. The brain board has no VBUS or ID detection for
it, so nothing tells Linux which role to take. The Tegra XUSB driver lets user space choose
(allow_userspace_control in drivers/phy/tegra/xusb.c), through
/sys/class/usb_role/usb2-0-role-switch/role. 'device' makes the Jetson a USB gadget behind the
hub, which is what L4T's USB device mode (network at 192.168.55.1, serial console) needs.
"""
import glob
import os

PREFERRED = 'usb2-0-role-switch'


def role_switch():
    path = f'/sys/class/usb_role/{PREFERRED}/role'
    if os.path.exists(path):
        return path
    found = sorted(glob.glob('/sys/class/usb_role/*/role'))
    return found[0] if len(found) == 1 else None


def get_role():
    path = role_switch()
    if not path:
        return None
    with open(path) as f:
        return f.read().strip()


def set_role(role):
    if role not in ('device', 'host', 'none'):
        raise ValueError(role)
    path = role_switch()
    if not path:
        raise FileNotFoundError('no USB role switch in /sys/class/usb_role (is usb2-0 set to otg with usb-role-switch?)')
    with open(path, 'w') as f:
        f.write(role)
    return path
