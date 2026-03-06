from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPixmap, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import write_overlay_settings_to_config
from ui.control_panel import OverlayControlPanel
from ui.overlay import SubtitleOverlay

def build_tray_icon(image_path: str) -> QIcon:
    if image_path:
        pix = QPixmap(image_path)
        if not pix.isNull():
            scaled = pix.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            canvas = QPixmap(32, 32)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            x = (32 - scaled.width()) // 2
            y = (32 - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.end()
            return QIcon(canvas)

    fallback = QPixmap(32, 32)
    fallback.fill(Qt.GlobalColor.transparent)
    painter = QPainter(fallback)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(24, 120, 255))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
    painter.drawText(fallback.rect(), Qt.AlignmentFlag.AlignCenter, "ASR")
    painter.end()
    return QIcon(fallback)


class TrayController(QObject):
    def __init__(
        self,
        app: QApplication,
        overlay: SubtitleOverlay,
        control_panel: OverlayControlPanel,
        config_path: Path,
        icon_path: str,
    ) -> None:
        super().__init__()
        self._app = app
        self._overlay = overlay
        self._control_panel = control_panel
        self._config_path = config_path

        self._tray = QSystemTrayIcon(build_tray_icon(icon_path), self._app)
        self._tray.setToolTip("Desktop Subtitle")
        self._menu = QMenu()
        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

        self._overlay.visibility_changed.connect(self._sync_states)
        self._control_panel.visibility_changed.connect(self._sync_states)
        self._sync_states()

    def _build_menu(self) -> None:
        self._action_toggle_overlay = QAction("", self._menu)
        self._action_toggle_overlay.triggered.connect(self._on_toggle_overlay)
        self._menu.addAction(self._action_toggle_overlay)

        self._action_open_settings = QAction("", self._menu)
        self._action_open_settings.triggered.connect(self._on_open_settings)
        self._menu.addAction(self._action_open_settings)

        self._menu.addSeparator()

        self._action_save = QAction("保存当前设置", self._menu)
        self._action_save.triggered.connect(self._on_save_settings)
        self._menu.addAction(self._action_save)

        self._action_quit = QAction("退出", self._menu)
        self._action_quit.triggered.connect(self._on_quit)
        self._menu.addAction(self._action_quit)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def _sync_states(self, _payload: Any = None) -> None:
        del _payload
        overlay_visible = self._overlay.isVisible()
        panel_visible = self._control_panel.isVisible()
        self._action_toggle_overlay.setText("隐藏字幕窗口" if overlay_visible else "显示字幕窗口")
        self._action_open_settings.setText("聚焦设置面板" if panel_visible else "打开设置面板")

    def _on_toggle_overlay(self) -> None:
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            self._overlay.show()
            self._overlay.raise_()
            self._overlay.activateWindow()
        self._sync_states()

    def _on_open_settings(self) -> None:
        if not self._overlay.isVisible():
            self._overlay.show()
        self._control_panel.move(self._overlay.x() + self._overlay.width() + 16, self._overlay.y())
        self._control_panel.show()
        self._control_panel.raise_()
        self._control_panel.activateWindow()
        self._sync_states()

    def _on_save_settings(self) -> None:
        try:
            write_overlay_settings_to_config(self._config_path, self._overlay.export_runtime_settings())
            self._tray.showMessage(
                "Desktop Subtitle",
                f"设置已保存到 {self._config_path}",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._tray.showMessage(
                "Desktop Subtitle",
                f"保存失败: {exc}",
                QSystemTrayIcon.MessageIcon.Critical,
                2800,
            )

    def _on_quit(self) -> None:
        self._app.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_toggle_overlay()
