from loguru import logger
from pathlib import Path
from typing import Union

from PySide6.QtCore import QCoreApplication, QObject, Signal

from RinUI import RinUIWindow
from src.core.directories import CW_PATH, DEFAULT_THEME
from src.core.plaza import MarkdownRenderBridge, PlazaBridge, TutorialRecommendationsBridge
from src.core.plugin.bridge import PluginBackendBridge


class ReleasableWindow(RinUIWindow):
    def __init__(self, central):
        # Auxiliary windows own their engine. Sharing the main engine couples
        # root-object creation and context lifetime across unrelated windows.
        super().__init__(shared_engine=False)
        self.central = central
        self.central.setup_qml_context(self)
        self.central.retranslate.connect(self.engine.retranslate)
        self._retranslate_connected = True
        self._released = False
        self._theme_window_handles: tuple[int, ...] = ()

        # RinUI's ThemeManager is a process-wide singleton. RinUIWindow connects
        # it once per window, so window churn otherwise accumulates duplicate
        # aboutToQuit callbacks. AppCentral owns the single shutdown call.
        app = QCoreApplication.instance()
        if app:
            try:
                app.aboutToQuit.disconnect(self.theme_manager.clean_up)
            except (RuntimeError, TypeError):
                pass
        logger.info("ReleasableWindow created")

    @property
    def is_released(self) -> bool:
        return self._released

    def load(self, qml_path: Union[str, Path] = None) -> None:
        super().load(qml_path)
        self._theme_window_handles = tuple(int(window.winId()) for window in self.windows)

    def release(self):
        if self._released:
            return
        self._released = True

        if self._retranslate_connected:
            try:
                self.central.retranslate.disconnect(self.engine.retranslate)
            except (RuntimeError, TypeError):
                pass
            self._retranslate_connected = False

        app = QCoreApplication.instance()
        if app and self.win_event_filter:
            app.removeNativeEventFilter(self.win_event_filter)
            self.win_event_filter = None
        if self.win_event_manager:
            self.win_event_manager.set_windows([])

        for handle in self._theme_window_handles:
            while handle in self.theme_manager.windows:
                self.theme_manager.windows.remove(handle)
        self._theme_window_handles = ()

        root_window = getattr(self, "root_window", None)
        if root_window:
            root_window.hide()
            root_window.releaseResources()
            root_window.deleteLater()
            self.root_window = None
        self.windows = []

        logger.info("ReleasableWindow released")
        self._cleanup_engine()

    def _cleanup_engine(self):
        self.engine.clearComponentCache()
        self.engine.collectGarbage()
        self.engine.deleteLater()


class ExamModeWindow(ReleasableWindow):
    """只显示时间、日期和退出按钮的无边框全屏考试时钟。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.load(CW_PATH / "Windows" / "ExamMode.qml")


class Settings(ReleasableWindow, QObject):
    extraSettingsChanged = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.bridge = PluginBackendBridge()

        self.engine.addImportPath(DEFAULT_THEME)
        self.engine.rootContext().setContextProperty(
            "UtilsBackend", self.central.utils_backend
        )
        self.engine.rootContext().setContextProperty(
            "UpdaterBridge", self.central.updater_bridge
        )
        self.engine.rootContext().setContextProperty("PluginBackendBridge", self.bridge)
        self.engine.rootContext().setContextProperty("Settings", self)
        self.extra_settings = []

        self.load(CW_PATH / "Windows" / "Settings.qml")
        logger.info("Settings window initialized")


class Editor(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)

        self.load(CW_PATH / "Windows" / "Editor.qml")


class PluginPlaza(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)
        self.plaza_bridge = PlazaBridge(self.central.configs)
        self.markdown_render_bridge = MarkdownRenderBridge()

        self.engine.rootContext().setContextProperty("PlazaBridge", self.plaza_bridge)
        self.engine.rootContext().setContextProperty("MarkdownRenderBridge", self.markdown_render_bridge)

        self.load(CW_PATH / "Windows" / "PluginPlaza.qml")

    def release(self):
        if self.is_released:
            return
        try:
            self.plaza_bridge.shutdown()
        finally:
            super().release()


class Tutorial(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)
        from RinUI import Theme
        self.setTheme(Theme.Auto)
        self.recommendations_bridge = TutorialRecommendationsBridge(self.central.configs)
        self.engine.rootContext().setContextProperty(
            "TutorialRecommendationsBridge", self.recommendations_bridge
        )

        self.load(CW_PATH / "Windows" / "Tutorial.qml")

    def release(self):
        if self.is_released:
            return
        try:
            self.recommendations_bridge.shutdown()
        finally:
            super().release()


class WhatsNew(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)
        self.engine.rootContext().setContextProperty(
            "UtilsBackend", self.central.utils_backend
        )

        self.load(CW_PATH / "Windows" / "WhatsNew.qml")


class CheckSingleInstanceDialog(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)

        self.load(
            CW_PATH
            / "Components"
            / "dialogs"
            / "CheckSingleInstanceDialog.qml"
        )


class ClassSwapWindow(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)

        self.load(
            CW_PATH
            / "Components"
            / "dialogs"
            / "ClassSwapDialog.qml"
        )


class ClassSwapRestoreDialog(ReleasableWindow):
    def __init__(self, parent):
        super().__init__(parent)

        self.load(
            CW_PATH
            / "Components"
            / "dialogs"
            / "ClassSwapRestoreDialog.qml"
        )
