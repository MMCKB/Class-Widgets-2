"""插件安装确认对话框。

当用户双击 .cwplugin 文件启动 Class Widgets 时，弹出此对话框显示插件信息并询问是否安装。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from loguru import logger

from src.core.directories import PLUGINS_PATH
from src.core.plugin.archive import PluginArchiveError, PluginArchiveInstaller


class PluginInstallDialog(QDialog):
    """插件安装确认对话框。

    展示 .cwplugin 归档的元数据（名称、版本、作者、描述），
    并提供「安装」和「取消」按钮。
    """

    def __init__(self, archive_path: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("安装插件")
        self.setMinimumWidth(480)
        self.setMinimumHeight(320)

        self.archive_path = Path(archive_path)
        self.installer = PluginArchiveInstaller(PLUGINS_PATH)
        self.plugin_info = None

        self._build_ui()
        self._load_archive_info()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("检测到插件文件")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 文件名
        self.file_name_label = QLabel(self.archive_path.name)
        self.file_name_label.setAlignment(Qt.AlignCenter)
        self.file_name_label.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(self.file_name_label)

        layout.addSpacing(8)

        # 信息表单
        form_widget = QWidget()
        self.form_layout = QFormLayout(form_widget)
        self.form_layout.setLabelAlignment(Qt.AlignRight)
        self.form_layout.setSpacing(8)
        layout.addWidget(form_widget)

        # 描述区域
        self.description_edit = QTextEdit()
        self.description_edit.setReadOnly(True)
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("（无描述）")
        layout.addWidget(self.description_edit)

        # 按钮
        button_box = QDialogButtonBox()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.install_btn = QPushButton("安装")
        self.install_btn.setDefault(True)
        self.install_btn.setStyleSheet(
            "QPushButton { background-color: #0078d4; color: white; "
            "padding: 6px 24px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #106ebe; }"
            "QPushButton:disabled { background-color: #ccc; color: #888; }"
        )
        self.install_btn.clicked.connect(self._on_install)

        button_box.addButton(self.cancel_btn, QDialogButtonBox.RejectRole)
        button_box.addButton(self.install_btn, QDialogButtonBox.AcceptRole)
        layout.addWidget(button_box)

    def _add_form_row(self, label: str, value: str) -> None:
        """向表单添加一行信息。"""
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        self.form_layout.addRow(f"{label}:", value_label)

    def _load_archive_info(self) -> None:
        """读取归档元数据并填充到 UI。"""
        try:
            self.plugin_info = self.installer.inspect(self.archive_path)
            self._add_form_row("名称", self.plugin_info.name)
            self._add_form_row("ID", self.plugin_info.plugin_id)
            self._add_form_row("版本", self.plugin_info.version)
            self._add_form_row("API 版本", self.plugin_info.api_version)

            manifest = self.plugin_info.manifest
            author = manifest.get("author", "")
            if author:
                self._add_form_row("作者", str(author))

            description = manifest.get("description", "")
            if description:
                self.description_edit.setText(str(description))
            else:
                self.description_edit.setVisible(False)

        except PluginArchiveError as exc:
            logger.error(f"Failed to inspect plugin archive: {exc}")
            self._add_form_row("错误", f"无法读取插件文件: {exc}")
            self.install_btn.setEnabled(False)
            QMessageBox.warning(self, "插件文件无效", str(exc))

    def _on_install(self) -> None:
        """执行安装。"""
        if not self.plugin_info:
            return
        try:
            result = self.installer.install(self.archive_path)
            msg = (
                f"插件 {result.plugin_id} v{result.version} 已安装"
                if not result.replaced
                else f"插件 {result.plugin_id} 已更新到 v{result.version}"
            )
            logger.info(msg)
            QMessageBox.information(self, "安装成功", msg)
            self.accept()
        except PluginArchiveError as exc:
            logger.error(f"Plugin installation failed: {exc}")
            QMessageBox.critical(self, "安装失败", str(exc))


def show_plugin_install_dialog(archive_path: str, parent: Optional[QObject] = None) -> None:
    """弹出插件安装确认对话框（便捷函数）。"""
    dialog = PluginInstallDialog(archive_path, parent)
    dialog.exec()
