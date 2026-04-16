# asahi-battery-tray

A lightweight system tray application for **Fedora Asahi Remix** on Apple Silicon. Provides hardware-level battery charge limiting via the `macsmc` driver. Basically AlDente, but native to Linux. Also like 90% vibe coded (including the vibe README).

Writes directly to sysfs control nodes with a state machine to prevent firmware oscillation. Zero runtime `sudo`, clean Qt/PySide6 UI, and seamless desktop integration.

## ✨ Features

- **Hardware Control**: Direct manipulation of `charge_control_end_threshold` and `charge_control_start_threshold`
- **Native Tray UI**: PySide6/Qt6 system tray icon for KDE and GNOME
- **Persistent Settings**: Configuration saved across reboots
- **Oscillation Prevention**: Dynamic threshold window stops rapid charge cycling at limits
- **No Runtime Sudo**: One-time udev rule grants user access to battery controls
- **Background Service**: systemd user service with auto-restart on failure

## 📦 Requirements

- Fedora Asahi Remix (Apple Silicon M1/M2/M3)
- Python 3.10+
- `python3-pyside6`, `qt6-qtbase` (installed automatically)

## 🚀 Installation

```bash
git clone https://github.com/bitz00/asahi-battery-tray.git
cd asahi-battery-tray
make install
```

That's it. The Makefile handles dependencies, file deployment, permissions, and service setup.

### Useful Commands

| Command | Description |
|---------|-------------|
| `make install` | Install everything |
| `make uninstall` | Remove all installed components |
| `make status` | Check service and udev rule status |
| `make clean` | Remove Python cache files |

## ▶️ Usage

- The app starts automatically on login, or run `battery-daemon.py` manually
- **Left-click** the tray icon to open the UI
- Adjust the charge limit slider (50–100%)
- If battery is above your limit, click **Discharge** to drain naturally to the target

## 🏗 Architecture

Three states manage safe kernel interaction:

1. **Charge**: System charges freely up to your set limit
2. **Hold**: At limit, sets tight window (`Start=Current`, `End=Current+1`) to maintain charge without engaging battery
3. **Discharge**: Drains battery until it reaches the limit, then returns to Hold

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Permission denied | Run `make install` again, or verify udev rule: `ls -l /sys/class/power_supply/macsmc-battery/` should show `rw-rw-rw-` |
| Tray icon missing | Ensure service is running: `make status`. Log out/in or restart the session |
| Service fails | Check logs: `journalctl --user -u battery-tray.service -e` |
| Settings not saving | Confirm service is enabled: `systemctl --user is-enabled battery-tray.service` |

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
