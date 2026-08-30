"""通用设置中的本地场景模式服务。"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from PySide6.QtCore import QObject, Property, Signal, Slot
from loguru import logger

from src.core.config.model import SceneMode

if TYPE_CHECKING:
    from src.core.central import AppCentral


class SceneModeService(QObject):
    """保存并恢复经过白名单限制的本地展示偏好和可管理的考试场景。"""

    EXAM_SCENE_ID = "exam-mode"
    EXAM_SCENE_KIND = "exam"

    changed = Signal()
    statusChanged = Signal()

    # 场景只控制本地展示与交互体验，不覆盖账号、网络、集控、通知、课程表或插件权限设置。
    _SUPPORTED_PREFERENCE_KEYS = (
        "current_theme",
        "scale_factor",
        "opacity",
        "widget_corner_radius",
        "widgets_anchor",
        "widgets_offset_x",
        "widgets_offset_y",
        "widgets_layer",
        "display",
        "mini_mode",
        "lighting_effect",
    )
    _SUPPORTED_INTERACTION_KEYS = ("hover_fade",)

    def __init__(self, app_central: "AppCentral") -> None:
        super().__init__(app_central)
        self._app_central = app_central
        self._status_text = ""
        self._ensure_exam_scene()

    @Property("QVariant", notify=changed)
    def scenes(self) -> list[dict[str, Any]]:
        return [scene.model_dump() for scene in self._configs.scene_modes.scenes]

    @Property(str, notify=changed)
    def activeSceneId(self) -> str:
        return self._configs.scene_modes.active_scene_id

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status_text

    @property
    def _configs(self):
        return self._app_central.configs

    def _set_status(self, text: str) -> None:
        if self._status_text != text:
            self._status_text = text
            self.statusChanged.emit()

    def _ensure_exam_scene(self) -> None:
        """为既有用户一次性添加可自行改名或删除的考试模式预设。"""
        scene_modes = self._configs.scene_modes
        if scene_modes.exam_preset_initialized:
            return
        if not any(scene.kind == self.EXAM_SCENE_KIND for scene in scene_modes.scenes):
            scene_modes.scenes.append(
                SceneMode(
                    id=self.EXAM_SCENE_ID,
                    name=self.tr("考试模式"),
                    kind=self.EXAM_SCENE_KIND,
                )
            )
        scene_modes.exam_preset_initialized = True
        self._configs.save(silent=True)

    def _save(self) -> None:
        self._configs.save(silent=True)
        self.changed.emit()

    def _scene_by_id(self, scene_id: str) -> SceneMode | None:
        return next((scene for scene in self._configs.scene_modes.scenes if scene.id == scene_id), None)

    def _capture_settings(self) -> dict[str, Any]:
        preferences = self._configs.preferences
        interactions = self._configs.interactions
        return {
            "preferences": {
                key: deepcopy(getattr(preferences, key))
                for key in self._SUPPORTED_PREFERENCE_KEYS
            },
            "interactions": {
                key: deepcopy(getattr(interactions, key))
                for key in self._SUPPORTED_INTERACTION_KEYS
            },
        }

    def _can_change(self, key: str) -> bool:
        if self._configs.isKeyLocked(key):
            logger.warning("Scene mode skipped locked key: {}", key)
            return False
        return True

    def _apply_settings(self, settings: dict[str, Any]) -> tuple[int, list[str]]:
        applied = 0
        skipped: list[str] = []
        preferences = settings.get("preferences", {})
        if isinstance(preferences, dict):
            selected_theme = preferences.get("current_theme")
            for key in self._SUPPORTED_PREFERENCE_KEYS:
                if key not in preferences or key == "current_theme":
                    continue
                config_key = f"preferences.{key}"
                if not self._can_change(config_key):
                    skipped.append(config_key)
                    continue
                self._configs.set(config_key, deepcopy(preferences[key]))
                applied += 1
            if isinstance(selected_theme, str) and selected_theme:
                if self._can_change("preferences.current_theme"):
                    if self._app_central.theme_manager.themeChange(selected_theme):
                        applied += 1
                    else:
                        skipped.append("preferences.current_theme（主题不存在）")
                else:
                    skipped.append("preferences.current_theme")

        interactions = settings.get("interactions", {})
        if isinstance(interactions, dict):
            for key in self._SUPPORTED_INTERACTION_KEYS:
                if key not in interactions:
                    continue
                config_key = f"interactions.{key}"
                if not self._can_change(config_key):
                    skipped.append(config_key)
                    continue
                self._configs.set(config_key, deepcopy(interactions[key]))
                applied += 1
        return applied, skipped

    @Slot(str, result=bool)
    def createScene(self, name: str) -> bool:
        normalized_name = name.strip()
        if not normalized_name:
            self._set_status("场景名称不能为空")
            return False
        if any(scene.name == normalized_name for scene in self._configs.scene_modes.scenes):
            self._set_status("已存在同名场景")
            return False
        scene = SceneMode(
            id=f"scene-{uuid4()}",
            name=normalized_name,
            settings=self._capture_settings(),
        )
        self._configs.scene_modes.scenes.append(scene)
        self._configs.scene_modes.active_scene_id = scene.id
        self._set_status(f"已保存场景“{normalized_name}”")
        self._save()
        return True

    @Slot(str, str, result=bool)
    def renameScene(self, scene_id: str, name: str) -> bool:
        scene = self._scene_by_id(scene_id)
        normalized_name = name.strip()
        if scene is None:
            self._set_status("未找到场景")
            return False
        if not normalized_name:
            self._set_status("场景名称不能为空")
            return False
        if any(other.id != scene_id and other.name == normalized_name for other in self._configs.scene_modes.scenes):
            self._set_status("已存在同名场景")
            return False
        scene.name = normalized_name
        self._set_status(f"已重命名场景为“{normalized_name}”")
        self._save()
        return True

    @Slot(str, result=bool)
    def updateSceneFromCurrent(self, scene_id: str) -> bool:
        scene = self._scene_by_id(scene_id)
        if scene is None:
            self._set_status("未找到场景")
            return False
        if scene.kind == self.EXAM_SCENE_KIND:
            self._set_status(f"场景“{scene.name}”不包含可更新的展示设置")
            return False
        scene.settings = self._capture_settings()
        self._set_status(f"已使用当前设置更新场景“{scene.name}”")
        self._save()
        return True

    @Slot(str, result=bool)
    def applyScene(self, scene_id: str) -> bool:
        scene = self._scene_by_id(scene_id)
        if scene is None:
            self._set_status("未找到场景")
            return False
        if scene.kind == self.EXAM_SCENE_KIND:
            if not self._app_central.examMode.enter():
                self._set_status(f"场景“{scene.name}”正在进入或已经启用")
                return False
            self._configs.scene_modes.active_scene_id = scene.id
            self._set_status(f"正在进入场景“{scene.name}”")
            self._save()
            return True
        applied, skipped = self._apply_settings(scene.settings)
        self._configs.scene_modes.active_scene_id = scene.id
        status = f"已应用场景“{scene.name}”（{applied} 项设置）"
        if skipped:
            status += f"；已跳过：{', '.join(skipped)}"
        self._set_status(status)
        self._save()
        return True

    @Slot(str, result=bool)
    def deleteScene(self, scene_id: str) -> bool:
        scene = self._scene_by_id(scene_id)
        if scene is None:
            self._set_status("未找到场景")
            return False
        self._configs.scene_modes.scenes = [item for item in self._configs.scene_modes.scenes if item.id != scene_id]
        if self._configs.scene_modes.active_scene_id == scene_id:
            self._configs.scene_modes.active_scene_id = ""
        self._set_status(f"已删除场景“{scene.name}”")
        self._save()
        return True
