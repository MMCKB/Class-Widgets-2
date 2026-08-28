from __future__ import annotations

import py_compile
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from src.core.central_control import CentralControlScheduleService, _CentralControlFetchWorker
from src.core.config.manager import RootConfig


PAGES_MANIFEST_URL = "https://mmckb.github.io/Test/manifest.json"


class FakeConfigs:
    def __init__(self) -> None:
        self.central_control = SimpleNamespace(
            schedule_manifest_url="",
            auto_fetch_enabled=False,
            auto_fetch_interval_minutes=15,
            allow_remote_power_commands=False,
            executed_command_ids=[],
        )
        self.save_calls: list[bool] = []

    def set(self, key: str, value: object) -> None:
        group, field_name = key.split(".", 1)
        setattr(getattr(self, group), field_name, value)

    def save(self, silent: bool = False) -> None:
        self.save_calls.append(silent)


class FakeNotificationManager:
    def __init__(self) -> None:
        self.configs = SimpleNamespace(
            notifications=SimpleNamespace(providers={})
        )
        self.providers = []
        self.dispatched = []

    def register_provider(self, provider: object) -> None:
        self.providers.append(provider)

    def dispatch(self, data: object, config: object) -> None:
        self.dispatched.append(data)


class FakeScheduleManager:
    def __init__(self, schedules_dir: Path) -> None:
        self.schedules_dir = schedules_dir
        self.loaded_name = ""

    def load(self, name: str, force: bool = False) -> bool:
        self.loaded_name = name
        return force and (self.schedules_dir / f"{name}.json").exists()


def test_python_syntax(project_root: Path) -> None:
    for source_file in (
        project_root / "src/core/central_control.py",
        project_root / "src/core/config/model.py",
        project_root / "src/core/config/manager.py",
        project_root / "src/core/central.py",
    ):
        py_compile.compile(str(source_file), doraise=True)


def test_remote_manifest_and_cache() -> None:
    payload = CentralControlScheduleService.fetch_manifest_payload(PAGES_MANIFEST_URL)
    assert len(payload["schedules"]) == 1
    assert payload["schedules"][0]["id"] == "class-schedule"
    assert payload["schedules"][0]["schedule"]["meta"]["version"] == 1
    assert len(payload["commands"]) == 1
    assert payload["commands"][0]["type"] == "announcement"
    assert payload["commands"][0]["id"]
    assert payload["commands"][0]["message"]

    with tempfile.TemporaryDirectory() as temp_dir:
        configs = FakeConfigs()
        manager = FakeScheduleManager(Path(temp_dir))
        notification_manager = FakeNotificationManager()
        service = CentralControlScheduleService(configs, manager, notification_manager)
        schedule_count, policy_version, auto_applied_name, match_status = service._cache_schedules(payload)
        schedule_name = "central_class-schedule"
        stored_schedule = manager.schedules_dir / f"{schedule_name}.json"
        assert schedule_count == 1
        assert policy_version == payload["policy_version"]
        assert auto_applied_name == ""
        assert match_status == "没有课表声明 yes.id=1"
        assert manager.loaded_name == "", "yes.id=0 or omitted must not switch schedules"
        assert stored_schedule.exists()
        assert service.centralSchedules[0]["id"] == "class-schedule"

        assert service.applyCentralSchedule("class-schedule") is True
        assert manager.loaded_name == schedule_name

        enabled_schedule = dict(payload["schedules"][0])
        enabled_schedule["yesId"] = 1
        second_schedule = dict(payload["schedules"][0])
        second_schedule["id"] = "class-schedule-2"
        second_schedule["name"] = "备用课程表"
        second_schedule["yesId"] = 0
        multi_payload = {
            "policy_version": payload["policy_version"],
            "schedules": [enabled_schedule, second_schedule],
            "commands": [],
        }

        manager.loaded_name = ""
        schedule_count, _, auto_applied_name, match_status = service._cache_schedules(multi_payload)
        assert schedule_count == 2
        assert auto_applied_name == schedule_name
        assert match_status == "唯一课表声明 yes.id=1"
        assert manager.loaded_name == schedule_name, "exactly one yes.id=1 schedule must switch"

        second_schedule["yesId"] = 1
        manager.loaded_name = ""
        _, _, auto_applied_name, match_status = service._cache_schedules(multi_payload)
        assert auto_applied_name == ""
        assert "有 2 份课表声明 yes.id=1" in match_status
        assert manager.loaded_name == "", "multiple yes.id=1 schedules must never switch"

        announcement_payload = {
            "commands": [
                {
                    "id": "announcement-test-001",
                    "type": "announcement",
                    "title": "集控公告",
                    "message": "原神牛逼",
                    "duration": 8000,
                    "expiresAt": None,
                }
            ]
        }
        announcement_count, power_action = service._apply_commands(announcement_payload)
        assert (announcement_count, power_action) == (1, "")
        assert len(notification_manager.dispatched) == 1
        assert notification_manager.dispatched[0].message == "原神牛逼"
        assert service._apply_commands(announcement_payload) == (0, "")
        assert configs.central_control.executed_command_ids == ["announcement-test-001"]


def test_power_commands() -> None:
    expires_at = "2099-01-01T00:00:00Z"
    valid_command = {
        "id": "power-test-001",
        "type": "power",
        "action": "sleep",
        "expiresAt": expires_at,
    }
    commands = CentralControlScheduleService._validate_commands([valid_command])
    assert commands == [valid_command]

    for invalid_command, expected_message in (
        ({**valid_command, "action": "shell"}, "集控电源命令动作无效"),
        ({**valid_command, "expiresAt": None}, "集控电源命令必须包含过期时间"),
    ):
        try:
            CentralControlScheduleService._validate_commands([invalid_command])
        except ValueError as exc:
            assert expected_message in str(exc)
        else:
            raise AssertionError(f"非法电源命令未被拒绝：{invalid_command}")

    with tempfile.TemporaryDirectory() as temp_dir:
        configs = FakeConfigs()
        manager = FakeScheduleManager(Path(temp_dir))
        notification_manager = FakeNotificationManager()
        service = CentralControlScheduleService(configs, manager, notification_manager)

        # 默认没有本机授权时，命令会被记为已处理但不会执行或发送通知。
        assert service._apply_commands({"commands": commands}) == (0, "")
        assert configs.central_control.executed_command_ids == ["power-test-001"]
        assert notification_manager.dispatched == []

        authorized_command = {**valid_command, "id": "power-test-002", "action": "restart"}
        configs.central_control.allow_remote_power_commands = True
        with patch("src.core.central_control.subprocess.Popen") as process:
            assert service._apply_commands({"commands": [authorized_command]}) == (0, "restart")
            process.assert_called_once_with(
                CentralControlScheduleService._power_command_arguments("restart"),
                close_fds=True,
            )
        assert configs.save_calls == [True]
        assert notification_manager.dispatched == []


def test_invalid_content_is_silently_rejected() -> None:
    completed: list[tuple[bool, str, object]] = []
    worker = _CentralControlFetchWorker("https://example.invalid/manifest.json")
    worker.completed.connect(lambda success, error, payload: completed.append((success, error, payload)))
    with patch.object(
        CentralControlScheduleService,
        "fetch_manifest_payload",
        side_effect=ValueError("课程表 yes.id 仅允许整数 0 或 1"),
    ):
        worker.run()

    assert completed == [(False, "", {"silentlyRejected": True})]
    with tempfile.TemporaryDirectory() as temp_dir:
        configs = FakeConfigs()
        manager = FakeScheduleManager(Path(temp_dir))
        notification_manager = FakeNotificationManager()
        service = CentralControlScheduleService(configs, manager, notification_manager)
        service._synced_schedules = {
            "previous": {
                "id": "previous",
                "name": "上次已同步课表",
                "localName": "central_previous",
                "sha256": "",
                "yesId": 0,
            }
        }
        service._last_announcement_count = 3
        service._set_status("上次同步状态")
        service._status_before_sync = service.statusText

        service._on_fetch_completed(*completed[0])

        assert service.statusText == "上次同步状态"
        assert service.centralSchedules[0]["id"] == "previous"
        assert service.lastAnnouncementCount == 3
        assert manager.loaded_name == ""
        assert notification_manager.dispatched == []


def test_configuration_and_qml(project_root: Path) -> None:
    config = RootConfig().central_control
    assert config.schedule_manifest_url == ""
    assert config.auto_fetch_enabled is False
    assert config.auto_fetch_interval_minutes == 15
    assert config.allow_remote_power_commands is False

    qml = (project_root / "src/qml/ClassWidgets/pages/settings/CentralControl.qml").read_text(
        encoding="utf-8"
    )
    for fragment in (
        "集控地址",
        "setManifestUrl",
        "setAutoFetchEnabled",
        "setAutoFetchIntervalMinutes",
        "fetchAndApplySchedule",
        "centralSchedules",
        "applyCentralSchedule",
        "lastMatchStatus",
        "自动拉取集控内容",
        "检查并同步集控内容",
        "yes.id 匹配结果",
        "yes.id=1",
        "远程电源命令",
        "allowRemotePowerCommands",
        "setAllowRemotePowerCommands",
    ):
        assert fragment in qml, f"Missing QML fragment: {fragment}"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    _application = QCoreApplication.instance() or QCoreApplication([])
    test_python_syntax(project_root)
    test_remote_manifest_and_cache()
    test_power_commands()
    test_invalid_content_is_silently_rejected()
    test_configuration_and_qml(project_root)
    print("Central-control schedule and announcement verification passed.")


if __name__ == "__main__":
    main()
