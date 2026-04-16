#!/usr/bin/env python3

import sys
import json
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu,
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QSpinBox,
    QPushButton, QLabel, QProgressBar, QFrame
)
from PySide6.QtCore import QTimer, Qt, QEvent
from PySide6.QtGui import QIcon, QCursor

# --- Paths ---
def find_battery_path():
    for p in ["/sys/class/power_supply/macsmc-battery", "/sys/class/power_supply/battery"]:
        if os.path.exists(p): return p
    for p in Path("/sys/class/power_supply").iterdir():
        if (p / "capacity").exists(): return str(p)
    return "/sys/class/power_supply/macsmc-battery"

BAT = find_battery_path()
END = f"{BAT}/charge_control_end_threshold"
START = f"{BAT}/charge_control_start_threshold"
CHARGE_NOW = f"{BAT}/charge_now"
CHARGE_FULL = f"{BAT}/charge_full"
CHARGE_FULL_DESIGN = f"{BAT}/charge_full_design"
ENERGY_NOW = f"{BAT}/energy_now"
ENERGY_FULL = f"{BAT}/energy_full"
STATUS = f"{BAT}/status"
CONFIG_FILE = Path.home() / ".config" / "battery-daemon.json"

if not os.path.exists(STATUS):
    for p in Path("/sys/class/power_supply").iterdir():
        if (p / "status").exists():
            STATUS = f"{p}/status"
            break

# --- Config ---
def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return {"limit": int(json.load(f).get("limit", 80))}
    except Exception:
        return {"limit": 80}

def save_config(limit):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"limit": limit}, f)

# --- SysFS Helpers ---
def read_int(path, fallback=-1):
    try:
        with open(path) as f: return int(float(f.read().strip()))
    except: return fallback

def read_str(path, fallback="Unknown"):
    try:
        with open(path) as f: return f.read().strip()
    except: return fallback

def write_int(path, value):
    try:
        with open(path, "w") as f: f.write(str(value))
        return True
    except Exception as e:
        print(f"❌ Write failed {path}: {e}", file=sys.stderr)
        return False

def get_live_charge_percent():
    now = read_int(CHARGE_NOW, -1)
    full = read_int(CHARGE_FULL, -1)
    if now > 0 and full > 0:
        return max(0, min(100, int((now / full) * 100)))
    if now > 0:
        full_design = read_int(CHARGE_FULL_DESIGN, -1)
        if full_design > 0:
            return max(0, min(100, int((now / full_design) * 100)))
    enow = read_int(ENERGY_NOW, -1)
    efull = read_int(ENERGY_FULL, -1)
    if enow > 0 and efull > 0:
        return max(0, min(100, int((enow / efull) * 100)))
    cap = read_int(f"{BAT}/capacity", -1)
    if 0 <= cap <= 100: return cap
    return -1

# --- UI Style ---
STYLE = """
QWidget#panel { background: #1e1e1e; border-radius: 10px; }
QProgressBar { border: none; border-radius: 3px; background: #2a2a2a; max-height: 5px; }
QProgressBar::chunk { border-radius: 3px; background: #10B981; }
QProgressBar[overlimit=true]::chunk { background: #F59E0B; }
QSlider::groove:horizontal { height: 4px; background: #2a2a2a; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: #10B981; border: 2px solid #1e1e1e; }
QSlider::sub-page:horizontal { background: #10B981; border-radius: 2px; }
QPushButton { border: none; border-radius: 6px; padding: 6px 10px; font-size: 12px; background: #2a2a2a; color: #e5e7eb; }
QPushButton:hover { background: #3a3a3a; }
QPushButton:pressed { background: #4a4a4a; }
QPushButton#close_btn { background: transparent; color: #9ca3af; font-size: 16px; padding: 2px; }
QPushButton#close_btn:hover { color: #ffffff; background: #3a3a3a; }
QPushButton#discharge_btn { border: 1px solid #F59E0B; color: #F59E0B; background: #1a1208; font-weight: 600; }
QPushButton#discharge_btn:hover { background: #2a1f12; }
QSpinBox { border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px 6px; font-size: 13px; min-width: 48px; background: #2a2a2a; color: #ffffff; }
QLabel { color: #e5e7eb; }
"""

# --- Panel ---
class BatteryPanel(QWidget):
    def __init__(self, tray):
        super().__init__()
        self.tray = tray
        self.cfg = load_config()
        self.target_limit = self.cfg["limit"]
        
        self.mode = 'CHARGE'
        self._applied_end = -1
        self._applied_start = -1
        self._warning_dismissed = False

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setObjectName("panel")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(260)
        self.installEventFilter(self)
        self._build_ui()

        QTimer.singleShot(300, self._init_state)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hide()
            return True
        if event.type() == QEvent.WindowDeactivate:
            self.hide()
            return True
        return super().eventFilter(obj, event)

    def _init_state(self):
        pct = get_live_charge_percent()
        if pct == -1: return
        
        self.mode = 'HOLD' if pct >= self.target_limit else 'CHARGE'
        self._apply_thresholds()
        self._update_ui_controls()
        self.refresh()

    def _update_ui_controls(self):
        self.slider.blockSignals(True)
        self.spinbox.blockSignals(True)
        self.slider.setValue(self.target_limit)
        self.spinbox.setValue(self.target_limit)
        self.slider.blockSignals(False)
        self.spinbox.blockSignals(False)
        self._highlight_preset(self.target_limit)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(0)

        header = QHBoxLayout()
        self.lbl_title = QLabel("Battery")
        self.lbl_title.setStyleSheet("font-size:13px;font-weight:500;")
        self.lbl_pct = QLabel("–")
        self.lbl_pct.setStyleSheet("font-size:12px;padding:2px 8px;border-radius:8px;background:#10B981;color:#ffffff;font-weight:600;")
        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_pct)
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("close_btn")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.hide)
        header.addWidget(self.btn_close)
        root.addLayout(header)
        root.addSpacing(6)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(5)
        root.addWidget(self.bar)
        root.addSpacing(4)

        self.lbl_status = QLabel("–")
        self.lbl_status.setStyleSheet("font-size:11px;color:#9ca3af;")
        root.addWidget(self.lbl_status)

        root.addSpacing(10)
        self._add_sep(root)
        root.addSpacing(10)

        lbl_section = QLabel("CHARGE LIMIT")
        lbl_section.setStyleSheet("font-size:9px;color:#6b7280;letter-spacing:1px;font-weight:600;")
        root.addWidget(lbl_section)
        root.addSpacing(8)

        ctrl_row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(50, 100)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setValue(self.target_limit)

        self.spinbox = QSpinBox()
        self.spinbox.setRange(50, 100)
        self.spinbox.setSuffix("%")
        self.spinbox.setValue(self.target_limit)

        self.slider.valueChanged.connect(self._on_slider)
        self.spinbox.valueChanged.connect(self._on_spinbox)

        ctrl_row.addWidget(self.slider)
        ctrl_row.addSpacing(6)
        ctrl_row.addWidget(self.spinbox)
        root.addLayout(ctrl_row)
        root.addSpacing(8)

        presets = QHBoxLayout()
        presets.setSpacing(6)
        self._preset_btns = {}
        for v in (80, 85, 100):
            btn = QPushButton(f"{v}%")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _, val=v: self._apply_preset(val))
            presets.addWidget(btn)
            self._preset_btns[v] = btn
        root.addLayout(presets)
        self._highlight_preset(self.target_limit)
        root.addSpacing(8)

        self.warn_frame = QFrame()
        self.warn_frame.setStyleSheet("QFrame { border: 1px solid #F59E0B; border-radius: 8px; background: #1a1208; }")
        warn_layout = QVBoxLayout(self.warn_frame)
        warn_layout.setContentsMargins(10, 8, 10, 8)
        warn_layout.setSpacing(6)

        self.lbl_warn = QLabel("Above limit")
        self.lbl_warn.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: 500;")
        warn_layout.addWidget(self.lbl_warn)

        self.btn_discharge = QPushButton("DISCHARGE TO LIMIT")
        self.btn_discharge.setObjectName("discharge_btn")
        self.btn_discharge.setFixedHeight(28)
        self.btn_discharge.clicked.connect(self._do_discharge)
        warn_layout.addWidget(self.btn_discharge)

        root.addWidget(self.warn_frame)
        self.warn_frame.hide()

    def _add_sep(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #2a2a2a;")
        layout.addWidget(line)

    def _on_slider(self, val):
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(val)
        self.spinbox.blockSignals(False)
        self._process_limit_change(val)

    def _on_spinbox(self, val):
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self._process_limit_change(val)

    def _apply_preset(self, val):
        self.slider.blockSignals(True)
        self.spinbox.blockSignals(True)
        self.slider.setValue(val)
        self.spinbox.setValue(val)
        self.slider.blockSignals(False)
        self.spinbox.blockSignals(False)
        self._process_limit_change(val)

    def _process_limit_change(self, val):
        self.target_limit = val
        save_config(val)
        self._highlight_preset(val)

        pct = get_live_charge_percent()
        self.mode = 'HOLD' if pct >= val else 'CHARGE'
        self._apply_thresholds()
        QTimer.singleShot(150, self.refresh)

    def _do_discharge(self):
        self.mode = 'DISCHARGE'
        self._warning_dismissed = True
        self.warn_frame.hide()
        self._apply_thresholds()
        print("🔻 Discharge requested. Letting battery coast.", file=sys.stderr)

    def _apply_thresholds(self):
        # 🔑 SECRET BUFFER LOGIC
        # UI shows 'self.target_limit', but we write 'target_limit + 2' to hardware.
        # This prevents the firmware from oscillating right at the limit.
        ui_limit = self.target_limit
        hidden_limit = ui_limit + 2
        if hidden_limit > 100:
            hidden_limit = 100
            
        # Always use START=0 to avoid macsmc discharge bugs
        target_start = 0
        target_end = hidden_limit

        if target_end != self._applied_end or target_start != self._applied_start:
            write_int(END, target_end)
            write_int(START, target_start)
            self._applied_end = target_end
            self._applied_start = target_start
            print(f"⚡ UI Limit: {ui_limit}% | HW Write: END={target_end}% | START={target_start}%", file=sys.stderr)

    def _highlight_preset(self, active):
        for val, btn in self._preset_btns.items():
            if val == active:
                btn.setStyleSheet("background:#10B981;color:#ffffff;font-weight:600;")
            else:
                btn.setStyleSheet("")

    def refresh(self):
        pct = get_live_charge_percent()
        status_raw = read_str(STATUS, "Unknown")
        
        print(f"📊 Kernel status: '{status_raw}'", file=sys.stderr)
        
        if pct == -1:
            self.lbl_status.setText("⚠ Cannot read battery")
            self.lbl_pct.setText("–")
            return

        # State transitions based on UI Limit
        if self.mode in ('CHARGE', 'DISCHARGE') and pct >= self.target_limit:
            self.mode = 'HOLD'
            print(f"🛑 Reached UI Limit ({self.target_limit}%) → HOLD", file=sys.stderr)
        elif self.mode == 'HOLD' and pct < self.target_limit:
            self.mode = 'CHARGE'
            print(f"🔋 Dropped below UI Limit ({self.target_limit}%) → CHARGE", file=sys.stderr)

        self._apply_thresholds()

        self.lbl_pct.setText(f"{pct}%")
        self.bar.setValue(pct)
        
        over = (pct > self.target_limit) and (self.target_limit < 100)
        self.bar.setProperty("overlimit", over)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)

        if not over:
            self._warning_dismissed = False

        self.lbl_status.setText(status_raw)

        if over and not self._warning_dismissed:
            self.warn_frame.show()
            self.lbl_warn.setText(f"{pct}% > {self.target_limit}% limit")
            self.lbl_pct.setStyleSheet("font-size:12px;padding:2px 8px;border-radius:8px;background:#F59E0B;color:#ffffff;font-weight:600;")
        else:
            self.warn_frame.hide()
            self.lbl_pct.setStyleSheet("font-size:12px;padding:2px 8px;border-radius:8px;background:#10B981;color:#ffffff;font-weight:600;")

        self.adjustSize()

    def show_above_tray(self):
        self.refresh()
        tray_geo = self.tray.geometry()
        if tray_geo and not tray_geo.isNull():
            x = tray_geo.center().x() - self.width() // 2
            y = tray_geo.top() - self.height() - 10
        else:
            pos = QCursor.pos()
            x = pos.x() - self.width() // 2
            y = pos.y() - self.height() - 10
        
        screen = QApplication.primaryScreen().geometry()
        if y < 0: y = 10
        if x < screen.left(): x = screen.left() + 10
        if x + self.width() > screen.right(): x = screen.right() - self.width() - 10
            
        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()


class BatteryTray(QSystemTrayIcon):
    def __init__(self):
        icon = QIcon.fromTheme("battery-full")
        if icon.isNull(): icon = QIcon.fromTheme("battery")
        super().__init__(icon)

        self._panel = BatteryPanel(self)

        menu = QMenu()
        menu.addAction("Show Battery", self._show_panel)
        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_tray_click)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._panel.refresh)
        self._timer.start(2000)

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_panel()

    def _show_panel(self):
        self._panel.show_above_tray()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    print(f"🔋 Battery path: {BAT}", file=sys.stderr)
    tray = BatteryTray()
    tray.setVisible(True)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
