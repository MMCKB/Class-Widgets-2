from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject

import src.core.exam_mode as exam_mode_module
from src.core.exam_mode import ExamModeService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeNotificationManager:
    def register_provider(self, provider) -> None:
        self.provider = provider


class FakeWindowManager:
    def __init__(self) -> None:
        self.open_calls = 0
        self.close_calls = 0

    def open_exam_mode(self) -> None:
        self.open_calls += 1

    def close_exam_mode(self) -> None:
        self.close_calls += 1


class FakeCentral(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.notification = FakeNotificationManager()
        self.window_manager = FakeWindowManager()


class FakeNotificationProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str, int, bool]] = []

    def push(self, level: int, title: str, message: str, duration: int, closable: bool) -> None:
        self.calls.append((level, title, message, duration, closable))


def test_exam_mode_lifecycle() -> None:
    central = FakeCentral()
    service = ExamModeService(central)
    provider = FakeNotificationProvider()
    service._notification_provider = provider

    original_set_volume = exam_mode_module.set_system_volume
    volume_changes: list[int] = []
    exam_mode_module.set_system_volume = lambda percent: volume_changes.append(percent) or True
    try:
        assert service.enter()
        assert service.entering
        assert not service.active
        assert volume_changes == [0]
        assert provider.calls == [
            (1, "考试模式", "正在进入考试模式…", service.ENTER_DELAY_MS, False)
        ]

        service._complete_entry(service._entry_token)
        assert service.active
        assert not service.entering
        assert central.window_manager.open_calls == 1

        assert service.exit()
        assert not service.active
        assert central.window_manager.close_calls == 1
    finally:
        exam_mode_module.set_system_volume = original_set_volume


def test_exam_mode_source_contract() -> None:
    central_source = (PROJECT_ROOT / "src/core/central.py").read_text(encoding="utf-8")
    scene_service_source = (PROJECT_ROOT / "src/core/scene_modes.py").read_text(encoding="utf-8")
    exam_service_source = (PROJECT_ROOT / "src/core/exam_mode.py").read_text(encoding="utf-8")
    volume_source = (PROJECT_ROOT / "src/core/system_volume.py").read_text(encoding="utf-8")
    window_manager_source = (PROJECT_ROOT / "src/core/windows/manager.py").read_text(encoding="utf-8")
    windows_source = (PROJECT_ROOT / "src/core/windows/windows.py").read_text(encoding="utf-8")
    exam_qml = (PROJECT_ROOT / "src/qml/ClassWidgets/Windows/ExamMode.qml").read_text(encoding="utf-8")

    assert '"com.classwidgets.exam-mode": "考试模式"' not in central_source
    assert "_request_exam_mode_shortcut" not in central_source
    assert "ExamModeService" in central_source
    assert "EXAM_SCENE_KIND" in scene_service_source
    assert "examMode.enter()" in scene_service_source
    assert "set_system_volume(0)" in exam_service_source
    assert "正在进入考试模式…" in exam_service_source
    assert "QTimer.singleShot" in exam_service_source
    assert "self._notification_provider.push" in exam_service_source
    assert "self._app_central.window_manager.open_exam_mode()" in exam_service_source
    assert 'sys.platform != "win32"' in volume_source
    assert "IAUDIO_ENDPOINT_VOLUME" in volume_source
    assert '"exam_mode"' in window_manager_source
    assert "ExamModeWindow" in windows_source
    assert "visibility: Window.FullScreen" in exam_qml
    assert "Qt.FramelessWindowHint" in exam_qml
    assert "Qt.Window |" not in exam_qml
    assert "minimumWidth: Screen.width" in exam_qml
    assert "maximumWidth: Screen.width" in exam_qml
    assert "minimumHeight: Screen.height" in exam_qml
    assert "maximumHeight: Screen.height" in exam_qml
    assert "AppCentral.timeService.currentTime" in exam_qml
    assert "AppCentral.timeService.currentDate" in exam_qml
    assert "退出考试模式" in exam_qml
    assert "Rectangle" not in exam_qml


def main() -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None
    test_exam_mode_lifecycle()
    test_exam_mode_source_contract()
    print("Exam mode verification passed.")


if __name__ == "__main__":
    main()
