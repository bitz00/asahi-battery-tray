# asahi-battery-tray

A lightweight system tray application designed for Fedora Asahi Remix running on Apple Silicon hardware. This utility provides direct hardware control over battery charging limits via the `macsmc` driver, replicating the functionality of tools such as AlDente.

It operates by writing directly to sysfs control nodes, utilizing a state machine to prevent firmware oscillation and ensuring a clean, native integration with the desktop environment.

## Features

- **Hardware-Level Control:** Direct interaction with `charge_control_end_threshold` and `charge_control_start_threshold`.
- **Native System Tray:** Clean Qt/PySide6 integration for KDE and GNOME desktop environments.
- **Persistent Configuration:** Settings are saved across reboots.
- **Oscillation Prevention:** Utilizes a dynamic threshold window to prevent the macSMC driver from rapid-cycling when at the charge limit.
- **Zero Privilege Escalation:** Uses a one-time udev rule to grant standard user access to battery controls, removing the need for sudo during operation.
- **Background Service:** Runs as a stable systemd user service with automatic restart on failure.

## Requirements

- **OS:** Fedora Asahi Remix (Fedora-based Asahi Linux installation).
- **Hardware:** Apple Silicon Mac (M1/M2/M3) with `macsmc` kernel support.
- **Python:** 3.10 or higher.
- **Dependencies:** PySide6 (Qt6 bindings for Python).

## Installation

### 1. Install Dependencies

Ensure you have the required Python libraries and Qt components. This script uses `dnf` as it is targeted at Fedora Asahi Remix.

```bash
sudo dnf install python3-pyside6 qt6-qtbase
```

### 2. Deploy the Application

Place the daemon script in your local user binary directory and ensure it is executable.

```bash
mkdir -p ~/.local/bin
# Assuming the file is named battery-daemon.py
cp battery-daemon.py ~/.local/bin/battery-daemon.py
chmod +x ~/.local/bin/battery-daemon.py
```

### 3. Configure Sysfs Permissions

By default, the battery control interface is read-only for standard users. Create a udev rule to grant write access.

Create the file `/etc/udev/rules.d/99-battery-permissions.rules` with the following content:

```udev
ACTION=="add|change", SUBSYSTEM=="power_supply", KERNEL=="macsmc-battery", RUN+="/bin/chmod a+w /sys/class/power_supply/macsmc-battery/charge_control_end_threshold /sys/class/power_supply/macsmc-battery/charge_control_start_threshold"
```

Apply the changes immediately without rebooting:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=power_supply
```

Verify the permissions have been applied:

```bash
ls -l /sys/class/power_supply/macsmc-battery/charge_control_end_threshold
```

### 4. Enable Systemd Service

To ensure the application runs in the background and persists across sessions, enable the user service.

Create the file `~/.config/systemd/user/battery-tray.service`:

```ini
[Unit]
Description=Asahi Battery Charge Limiter
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 /home/%U/.local/bin/battery-daemon.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Reload the systemd daemon and start the service:

```bash
systemctl --user daemon-reload
systemctl --user enable --now battery-tray.service
```

### 5. Configure Autostart (Desktop Entry)

For the tray icon to appear reliably upon login in KDE/GNOME, add a desktop entry.

Create the file `~/.config/autostart/battery-tray.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Battery Tray
Exec=python3 /home/%U/.local/bin/battery-daemon.py
NoDisplay=true
X-KDE-autostart-enabled=true
X-GNOME-Autostart-enabled=true
StartupNotify=false
Hidden=true
```

## Usage

1.  **Launch:** The application will start automatically on your next login, or you can run `python3 ~/.local/bin/battery-daemon.py` immediately.
2.  **Open UI:** Left-click the battery icon in the system tray.
3.  **Set Limit:** Use the slider or input field to select a charge cap between 50% and 100%.
4.  **Discharge Mode:** If the current battery level is above the set limit, a "Discharge" button will appear. Clicking this allows the system to drain to the limit naturally.

## Architecture

The application manages three distinct states to interact with the kernel safely:

- **Charge:** The system charges freely up to the user-defined limit.
- **Hold:** Once the limit is reached, the system sets a tight threshold window (`Start=Current`, `End=Current+1`) to maintain the current charge level without engaging the battery.
- **Discharge:** Allows the battery to drain until it reaches the configured limit, at which point it returns to the Hold state.

## Troubleshooting

| Issue | Resolution |
| :--- | :--- |
| **Permission Denied** | Verify the udev rule is applied and permissions are `rw-rw-rw-` using `ls -l /sys/class/power_supply/macsmc-battery/`. |
| **Tray Icon Missing** | Ensure `X-KDE-autostart-enabled=true` is set and the `.desktop` file is executable. |
| **Service Fails** | Check logs via `journalctl --user -u battery-tray.service -e` to identify Python tracebacks. |
| **Settings Lost on Reboot** | Ensure the systemd service is enabled via `systemctl --user enable battery-tray.service`. |

## License

This project is licensed under the MIT License    
