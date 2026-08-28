from __future__ import annotations

import importlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace


class FakeNotificationManager:
    def __init__(self) -> None:
        self.configs = SimpleNamespace(notifications=SimpleNamespace(providers={}))

    def register_provider(self, _provider: object) -> None:
        pass

    def dispatch(self, _data: object, _config: object = None) -> None:
        pass


class FakeCentral:
    def __init__(self) -> None:
        self.notification = FakeNotificationManager()
        self.runtime = SimpleNamespace(current_status=None, current_day=None, current_offset_time=None)


def test_plugin_project_registration_and_persistence() -> None:
    service_module = importlib.import_module("src.core.automations.user_profiles")
    with tempfile.TemporaryDirectory() as temp_dir:
        original_configs_path = service_module.CONFIGS_PATH
        service_module.CONFIGS_PATH = Path(temp_dir)
        try:
            callbacks: list[bool] = []
            opened: list[bool] = []
            service = service_module.AutomationProfilesService(FakeCentral())
            project_id = service.register_plugin_project(
                plugin_id="org.example.exam",
                project_id="exam-mode",
                title="考试模式",
                description="考试时由插件接管提醒。",
                on_enabled_changed=callbacks.append,
                on_open_settings=lambda: opened.append(True),
            )
            assert project_id == "org.example.exam.exam-mode"
            assert callbacks == [False]
            assert service.pluginProjects == [
                {
                    "id": project_id,
                    "pluginId": "org.example.exam",
                    "title": "考试模式",
                    "description": "考试时由插件接管提醒。",
                    "icon": "ic_fluent_plug_connected_20_regular",
                    "enabled": False,
                    "hasSettings": True,
                }
            ]
            assert service.setPluginProjectEnabled(project_id, True) is True
            assert callbacks == [False, True]
            assert service.openPluginProjectSettings(project_id) is True
            assert opened == [True]

            state_path = Path(temp_dir) / "automation_plugin_projects.json"
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            assert persisted["schemaVersion"] == 1
            assert persisted["projects"] == {project_id: True}

            restored_callbacks: list[bool] = []
            restored = service_module.AutomationProfilesService(FakeCentral())
            restored_id = restored.register_plugin_project(
                plugin_id="org.example.exam",
                project_id="exam-mode",
                title="考试模式",
                on_enabled_changed=restored_callbacks.append,
            )
            assert restored_id == project_id
            assert restored.pluginProjects[0]["enabled"] is True
            assert restored_callbacks == [True]

            restored.unregister_plugin_projects("org.example.exam")
            assert restored.pluginProjects == []
            persisted_after_unload = json.loads(state_path.read_text(encoding="utf-8"))
            assert persisted_after_unload["projects"] == {project_id: True}
        finally:
            service_module.CONFIGS_PATH = original_configs_path


def test_plugin_trigger_and_action_registration() -> None:
    service_module = importlib.import_module("src.core.automations.user_profiles")
    with tempfile.TemporaryDirectory() as temp_dir:
        original_configs_path = service_module.CONFIGS_PATH
        service_module.CONFIGS_PATH = Path(temp_dir)
        try:
            service = service_module.AutomationProfilesService(FakeCentral())
            trigger_id = service.register_plugin_trigger(
                "org.example.plugin", "focus-started", "专注已开始", "插件检测到专注状态。"
            )
            calls: list[dict] = []
            action_id = service.register_plugin_action(
                "org.example.plugin", "focus-action", "记录专注状态", calls.append
            )
            assert trigger_id == "plugin.org.example.plugin.focus-started"
            assert action_id == "plugin.org.example.plugin.focus-action"
            assert trigger_id in [item["id"] for item in service.triggerOptions]
            assert action_id in [item["id"] for item in service.actionOptions]

            profile = service_module.AutomationProfile(
                name="插件规则",
                enabled=True,
                rules=[
                    service_module.AutomationRule(
                        trigger=service_module.AutomationTrigger(type=trigger_id),
                        actions=[service_module.AutomationAction(type=action_id)],
                        cooldown_seconds=0,
                    )
                ],
            )
            service._profiles[profile.id] = profile
            service._running = True
            assert service.emit_plugin_trigger("org.example.plugin", "focus-started") is True
            assert len(calls) == 1
            assert calls[0]["action"]["type"] == action_id
            assert service.emit_plugin_trigger("org.example.plugin", "missing") is False

            service.unregister_plugin_projects("org.example.plugin")
            assert trigger_id not in [item["id"] for item in service.triggerOptions]
            assert action_id not in [item["id"] for item in service.actionOptions]
        finally:
            service_module.CONFIGS_PATH = original_configs_path


def test_plugin_api_namespaces_and_validates_projects() -> None:
    service_module = importlib.import_module("src.core.automations.user_profiles")
    components = importlib.import_module("src.core.plugin.components")
    with tempfile.TemporaryDirectory() as temp_dir:
        original_configs_path = service_module.CONFIGS_PATH
        service_module.CONFIGS_PATH = Path(temp_dir)
        try:
            service = service_module.AutomationProfilesService(FakeCentral())
            manager = SimpleNamespace(init_user_profiles=lambda: service)
            plugin = SimpleNamespace(meta={"id": "org.example.plugin"})
            plugin_api = SimpleNamespace(
                _app=SimpleNamespace(automation_manager=manager),
                current_plugin=plugin,
            )
            api = components.AutomationAPI(plugin_api)
            project_id = api.register_project("focus", "专注模式")
            assert project_id == "org.example.plugin.focus"
            trigger_id = api.register_trigger("focus-started", "专注已开始")
            action_id = api.register_action("focus-action", "记录专注", lambda _context: True)
            assert trigger_id == "plugin.org.example.plugin.focus-started"
            assert action_id == "plugin.org.example.plugin.focus-action"
            assert api.emit_trigger(trigger_id) is True
            plugin_api.current_plugin = None
            assert api.emit_trigger(trigger_id) is True

            try:
                api.register_project("../../unsafe", "不应注册")
            except ValueError:
                pass
            else:
                raise AssertionError("unsafe plugin project ID must be rejected")

            api.unregister_plugin_projects("org.example.plugin")
            assert service.pluginProjects == []
            assert trigger_id not in [item["id"] for item in service.triggerOptions]
            assert action_id not in [item["id"] for item in service.actionOptions]
        finally:
            service_module.CONFIGS_PATH = original_configs_path


def test_source_and_qml_contract(project_root: Path) -> None:
    components = (project_root / "src/core/plugin/components.py").read_text(encoding="utf-8")
    manager = (project_root / "src/core/plugin/manager.py").read_text(encoding="utf-8")
    service = (project_root / "src/core/automations/user_profiles.py").read_text(encoding="utf-8")
    page = (project_root / "src/qml/ClassWidgets/pages/settings/Automation.qml").read_text(encoding="utf-8")
    documentation = (project_root / "README_PLUGIN_AUTOMATION_PROJECTS.md").read_text(encoding="utf-8")

    assert "def register_project(" in components
    assert "def unregister_plugin_projects(" in components
    assert "def register_trigger(" in components
    assert "def emit_trigger(" in components
    assert "def register_action(" in components
    assert "register_plugin_project(" in components
    assert "unregister_plugin_projects(pid)" in manager
    assert "unregister_plugin_projects(plugin_id)" in manager
    assert "class PluginAutomationProject" in service
    assert "def register_plugin_project(" in service
    assert "def setPluginProjectEnabled(" in service
    assert "def openPluginProjectSettings(" in service
    assert "def register_plugin_trigger(" in service
    assert "def emit_plugin_trigger(" in service
    assert "def emit_registered_plugin_trigger(" in service
    assert "def register_plugin_action(" in service
    assert "triggerOptions" in service
    assert "actionOptions" in service
    assert "automation_plugin_projects.json" in service
    assert "插件自动化项目" in page
    assert "pluginProjects" in page
    assert "setPluginProjectEnabled" in page
    assert "openPluginProjectSettings" in page
    assert "triggerOptions" in page
    assert "actionOptions" in page
    assert page.count("{") == page.count("}"), "unbalanced QML braces"
    assert "插件自动化扩展开发指南" in documentation
    assert "register_project" in documentation
    assert "register_trigger" in documentation
    assert "emit_trigger" in documentation
    assert "register_action" in documentation
    assert "on_enabled_changed" in documentation
    assert "on_open_settings" in documentation
    assert "安全边界" in documentation


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    test_plugin_project_registration_and_persistence()
    test_plugin_trigger_and_action_registration()
    test_plugin_api_namespaces_and_validates_projects()
    test_source_and_qml_contract(project_root)
    print("Plugin automation projects verification passed.")


if __name__ == "__main__":
    main()
