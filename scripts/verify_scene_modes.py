from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject

from src.core.config.manager import RootConfig
from src.core.scene_modes import SceneModeService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeConfigs:
    def __init__(self) -> None:
        self._config = RootConfig()
        self.locked: set[str] = set()
        self.save_calls = 0

    def __getattr__(self, name: str):
        return getattr(self._config, name)

    def isKeyLocked(self, key: str) -> bool:
        return key in self.locked

    def set(self, key: str, value) -> None:
        target = self._config
        parts = key.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], value)

    def save(self, silent: bool = False) -> None:
        assert silent
        self.save_calls += 1


class FakeThemeManager:
    def __init__(self, configs: FakeConfigs) -> None:
        self.configs = configs
        self.applied_themes: list[str] = []

    def themeChange(self, theme_id: str) -> bool:
        if theme_id == "missing.theme":
            return False
        self.applied_themes.append(theme_id)
        self.configs.preferences.current_theme = theme_id
        return True


class FakeExamMode:
    def __init__(self) -> None:
        self.enter_calls = 0

    def enter(self) -> bool:
        self.enter_calls += 1
        return True


class FakeCentral(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.configs = FakeConfigs()
        self.theme_manager = FakeThemeManager(self.configs)
        self.examMode = FakeExamMode()


def test_scene_mode_lifecycle() -> None:
    central = FakeCentral()
    configs = central.configs
    configs.preferences.current_theme = "theme.classroom"
    configs.preferences.scale_factor = 1.15
    configs.preferences.opacity = 0.82
    configs.preferences.widgets_offset_x = 16
    configs.interactions.hover_fade = True

    service = SceneModeService(central)
    assert len(service.scenes) == 1
    exam_scene = service.scenes[0]
    assert exam_scene["id"] == "exam-mode"
    assert exam_scene["kind"] == "exam"
    assert configs.scene_modes.exam_preset_initialized is True

    assert service.createScene("上课展示")
    assert len(service.scenes) == 2
    scene_id = service.activeSceneId
    assert scene_id.startswith("scene-")
    assert configs.save_calls == 2

    configs.preferences.current_theme = "theme.home"
    configs.preferences.scale_factor = 0.9
    configs.preferences.opacity = 0.5
    configs.preferences.widgets_offset_x = 0
    configs.interactions.hover_fade = False
    assert service.applyScene(scene_id)
    assert configs.preferences.current_theme == "theme.classroom"
    assert configs.preferences.scale_factor == 1.15
    assert configs.preferences.opacity == 0.82
    assert configs.preferences.widgets_offset_x == 16
    assert configs.interactions.hover_fade is True
    assert central.theme_manager.applied_themes == ["theme.classroom"]
    assert "已应用场景“上课展示”" in service.statusText

    configs.preferences.opacity = 0.35
    configs.locked.add("preferences.opacity")
    assert service.applyScene(scene_id)
    assert configs.preferences.opacity == 0.35
    assert "preferences.opacity" in service.statusText

    configs.locked.clear()
    configs.preferences.scale_factor = 1.4
    assert service.updateSceneFromCurrent(scene_id)
    configs.preferences.scale_factor = 1.0
    assert service.applyScene(scene_id)
    assert configs.preferences.scale_factor == 1.4

    assert not service.createScene("上课展示")
    assert "同名场景" in service.statusText
    assert service.renameScene(scene_id, "演示模式")
    assert next(scene for scene in service.scenes if scene["id"] == scene_id)["name"] == "演示模式"
    assert service.deleteScene(scene_id)
    assert len(service.scenes) == 1
    assert service.activeSceneId == ""

    exam_scene_id = service.scenes[0]["id"]
    assert service.renameScene(exam_scene_id, "静音时钟")
    assert service.applyScene(exam_scene_id)
    assert central.examMode.enter_calls == 1
    assert service.activeSceneId == exam_scene_id
    assert not service.updateSceneFromCurrent(exam_scene_id)
    assert service.deleteScene(exam_scene_id)
    assert service.scenes == []

    # 用户删除考试预设后不自动重新创建。
    replacement_service = SceneModeService(central)
    assert replacement_service.scenes == []


def test_scene_configuration_defaults() -> None:
    config = RootConfig.model_validate({"preferences": {"opacity": 0.7}})
    assert config.scene_modes.scenes == []
    assert config.scene_modes.active_scene_id == ""
    assert config.scene_modes.exam_preset_initialized is False


def test_qml_navigation_contract() -> None:
    settings_qml = (PROJECT_ROOT / "src/qml/ClassWidgets/Windows/Settings.qml").read_text(encoding="utf-8")
    scene_qml = (PROJECT_ROOT / "src/qml/ClassWidgets/pages/settings/General/SceneModes.qml").read_text(encoding="utf-8")
    tray_qml = (PROJECT_ROOT / "src/qml/ClassWidgets/Windows/TrayPanel.qml").read_text(encoding="utf-8")
    scene_service = (PROJECT_ROOT / "src/core/scene_modes.py").read_text(encoding="utf-8")

    assert 'title: qsTr("场景模式")' in settings_qml
    assert 'pages/settings/General/SceneModes.qml' in settings_qml
    assert 'AppCentral.sceneModes' in scene_qml
    assert 'createScene' in scene_qml
    assert 'applyScene' in scene_qml
    assert 'updateSceneFromCurrent' in scene_qml
    assert 'deleteScene' in scene_qml
    assert '进入考试模式' in scene_qml
    assert 'EXAM_SCENE_KIND' in scene_service
    assert '_ensure_exam_scene' in scene_service
    assert 'text: qsTr("切换场景")' in tray_qml
    assert 'visible: sceneData.length > 0' in tray_qml
    assert 'AppCentral.sceneModes.scenes' in tray_qml
    assert 'AppCentral.sceneModes.applyScene' in tray_qml
    assert '_SUPPORTED_PREFERENCE_KEYS' in scene_service
    assert 'network' not in scene_service.split('_SUPPORTED_PREFERENCE_KEYS', 1)[1].split('_SUPPORTED_INTERACTION_KEYS', 1)[0]


def main() -> None:
    test_scene_configuration_defaults()
    test_scene_mode_lifecycle()
    test_qml_navigation_contract()
    print("Scene modes verification passed.")


if __name__ == "__main__":
    main()
