SHELL := /bin/bash
.PHONY: install uninstall deps status help clean

# Project files
SCRIPT       := battery-daemon.py
UDEV_RULE    := 99-battery-permissions.rules
SERVICE_FILE := battery-tray.service
DESKTOP_FILE := battery-tray.desktop

# Target directories
BIN_DIR      := $(HOME)/.local/bin
UDEV_DIR     := /etc/udev/rules.d
SYSTEMD_DIR  := $(HOME)/.config/systemd/user
AUTOSTART_DIR:= $(HOME)/.config/autostart

deps:
	@echo "📦 Installing system dependencies..."
	@sudo dnf install -y python3-pyside6 qt6-qtbase

install: deps
	@test -f $(SCRIPT) || { echo "❌ Error: $(SCRIPT) not found."; exit 1; }
	@mkdir -p $(BIN_DIR) $(SYSTEMD_DIR) $(AUTOSTART_DIR)
	@echo "📜 Installing daemon script..."
	@cp -f $(SCRIPT) $(BIN_DIR)/
	@chmod +x $(BIN_DIR)/$(SCRIPT)
	@echo "🔧 Deploying udev rule (requires sudo)..."
	@sudo cp -f udev/$(UDEV_RULE) $(UDEV_DIR)/
	@sudo udevadm control --reload-rules
	@sudo udevadm trigger --subsystem-match=power_supply
	@echo "⚙️  Installing systemd user service..."
	@cp -f systemd/user/$(SERVICE_FILE) $(SYSTEMD_DIR)/
	@systemctl --user daemon-reload
	@systemctl --user enable --now battery-tray.service
	@echo "🖼️  Installing autostart desktop entry..."
	@cp -f autostart/$(DESKTOP_FILE) $(AUTOSTART_DIR)/
	@echo ""
	@echo "✅ Installation complete!"

uninstall:
	@echo "🗑️  Removing installed files..."
	@rm -f $(BIN_DIR)/$(SCRIPT)
	@sudo rm -f $(UDEV_DIR)/$(UDEV_RULE)
	@systemctl --user stop battery-tray.service 2>/dev/null || true
	@systemctl --user disable battery-tray.service 2>/dev/null || true
	@rm -f $(SYSTEMD_DIR)/$(SERVICE_FILE)
	@rm -f $(AUTOSTART_DIR)/$(DESKTOP_FILE)
	@systemctl --user daemon-reload
	@sudo udevadm control --reload-rules
	@echo "✅ Uninstallation complete."

status:
	@systemctl --user status battery-tray.service --no-pager -l
	@echo ""
	@ls -l $(UDEV_DIR)/$(UDEV_RULE) 2>/dev/null || echo "udev rule not found"

help:
	@echo "Available targets:"
	@echo "  make install    - Install everything"
	@echo "  make uninstall  - Remove everything"
	@echo "  make status     - Check service status"
	@echo "  make deps       - Install dependencies only"
	@echo "  make clean      - Remove Python cache"
