"""快捷面板触发的全屏沉浸式考试模式。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer

from src.core.notification.model import NotificationLevel
from src.core.notification.provider import NotificationProvider
from src.core.system_volume import set_system_volume

if TYPE_CHECKING:
    from src.core.central import AppCentral


class ExamModeService(QObject):
    """控制考试模式的进入通知、静音与全屏时钟窗口。"""

    ENTER_DELAY_MS = 700

    changed = Signal()

    def __init__(self, app_central: "AppCentral") -> None:
        super().__init__(app_central)
        self._app_central = app_central
        self._active = False
        self._entering = False
        self._entry_token = 0
        self._notification_provider = NotificationProvider(
            id="com.classwidgets.exam-mode",
            name=self.tr("考试模式"),
            icon="ic_fluent_timer_20_regular",
            use_system_notify=False,
            manager=app_central.notification,
        )

    @Property(bool, notify=changed)
    def active(self) -> bool:
        return self._active

    @Property(bool, notify=changed)
    def entering(self) -> bool:
        return self._entering

    @Slot(result=bool)
    def enter(self) -> bool:
        """提示用户、静音系统输出，并在提示结束后进入全屏时钟。"""
        if self._active or self._entering:
            return False

        self._entering = True
        self._entry_token += 1
        entry_token = self._entry_token
        self.changed.emit()

        set_system_volume(0)
        self._notification_provider.push(
            int(NotificationLevel.ANNOUNCEMENT),
            self.tr("考试模式"),
            self.tr("正在进入考试模式…"),
            self.ENTER_DELAY_MS,
            False,
        )
        QTimer.singleShot(self.ENTER_DELAY_MS, lambda: self._complete_entry(entry_token))
        return True

    def _complete_entry(self, entry_token: int) -> None:
        if entry_token != self._entry_token or not self._entering:
            return
        self._entering = False
        self._active = True
        self._app_central.window_manager.open_exam_mode()
        self.changed.emit()

    @Slot(result=bool)
    def exit(self) -> bool:
        """关闭沉浸时钟；系统音量保持用户进入时要求的静音状态。"""
        if not self._active and not self._entering:
            return False
        self._entry_token += 1
        self._entering = False
        self._active = False
        self._app_central.window_manager.close_exam_mode()
        self.changed.emit()
        return True
