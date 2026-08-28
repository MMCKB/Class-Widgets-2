from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import requests
from loguru import logger
from PySide6.QtCore import QObject, Property, QThread, QTimer, Signal, Slot

from src import __SCHEDULE_SCHEMA_VERSION__
from src.core.notification import NotificationProvider
from src.core.notification.model import NotificationLevel
from src.core.schedule.model import ScheduleData

if TYPE_CHECKING:
    from src.core.config.manager import ConfigManager
    from src.core.notification.manager import NotificationManager
    from src.core.schedule.manager import ScheduleManager


MAX_SCHEDULE_BYTES = 2 * 1024 * 1024
MAX_SCHEDULES = 20
MAX_COMMANDS = 20
MAX_COMMAND_TEXT_LENGTH = 500
MAX_EXECUTED_COMMAND_IDS = 100
_POWER_COMMAND_TYPES = {"restart", "shutdown", "hibernate", "sleep"}
_SCHEDULE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_COMMAND_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class _CentralControlFetchWorker(QThread):
    completed = Signal(bool, str, object)

    def __init__(self, manifest_url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.manifest_url = manifest_url

    def run(self) -> None:
        try:
            payload = CentralControlScheduleService.fetch_manifest_payload(self.manifest_url)
        except ValueError as exc:
            # 集控内容本身不合规则静默丢弃，避免不可信下发内容造成用户可见提示。
            logger.warning("Rejected invalid central-control content: {}", exc)
            self.completed.emit(False, "", {"silentlyRejected": True})
            return
        except Exception as exc:
            self.completed.emit(False, str(exc), {})
            return
        self.completed.emit(True, "", payload)


class CentralControlScheduleService(QObject):
    """从静态集控清单接收课程表和一次性公告命令。"""

    changed = Signal()
    applied = Signal(str)

    def __init__(
        self,
        configs: "ConfigManager",
        schedule_manager: "ScheduleManager",
        notification_manager: "NotificationManager",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._configs = configs
        self._schedule_manager = schedule_manager
        self._worker: _CentralControlFetchWorker | None = None
        self._syncing = False
        self._status_text = self.tr("尚未检查集控内容")
        self._status_before_sync = self._status_text
        self._last_applied_name = ""
        self._last_policy_version = ""
        self._last_announcement_count = 0
        self._last_match_status = ""
        self._synced_schedules: dict[str, dict] = {}
        self._auto_fetch_timer = QTimer(self)
        self._auto_fetch_timer.timeout.connect(self.fetchAndApplySchedule)
        self._notification_provider = NotificationProvider(
            id="com.classwidgets.central-control",
            name=self.tr("集控公告"),
            icon="ic_fluent_megaphone_20_regular",
            use_system_notify=True,
            manager=notification_manager,
        )

    @Property(str, notify=changed)
    def manifestUrl(self) -> str:
        return self._configs.central_control.schedule_manifest_url

    @Property(bool, notify=changed)
    def autoFetchEnabled(self) -> bool:
        return self._configs.central_control.auto_fetch_enabled

    @Property(int, notify=changed)
    def autoFetchIntervalMinutes(self) -> int:
        return self._configs.central_control.auto_fetch_interval_minutes

    @Property(bool, notify=changed)
    def syncing(self) -> bool:
        return self._syncing

    @Property(str, notify=changed)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=changed)
    def lastAppliedName(self) -> str:
        return self._last_applied_name

    @Property(str, notify=changed)
    def lastPolicyVersion(self) -> str:
        return self._last_policy_version

    @Property(int, notify=changed)
    def lastAnnouncementCount(self) -> int:
        return self._last_announcement_count

    @Property(bool, notify=changed)
    def allowRemotePowerCommands(self) -> bool:
        return self._configs.central_control.allow_remote_power_commands

    @Property(list, notify=changed)
    def centralSchedules(self) -> list[dict]:
        """本次成功同步的多个集控课表；仅在用户操作时切换。"""
        return [dict(schedule) for schedule in self._synced_schedules.values()]

    @Property(str, notify=changed)
    def lastMatchStatus(self) -> str:
        return self._last_match_status

    def start(self) -> None:
        """在配置加载后启动自动拉取；手动模式不产生网络请求。"""
        self._configure_auto_fetch(fetch_immediately=True)

    def stop(self) -> None:
        self._auto_fetch_timer.stop()

    @Slot(str)
    def setManifestUrl(self, manifest_url: str) -> None:
        self._configs.set("central_control.schedule_manifest_url", manifest_url.strip())
        self._configure_auto_fetch(fetch_immediately=True)
        self.changed.emit()

    @Slot(bool)
    def setAutoFetchEnabled(self, enabled: bool) -> None:
        self._configs.set("central_control.auto_fetch_enabled", enabled)
        self._configure_auto_fetch(fetch_immediately=True)
        self.changed.emit()

    @Slot(int)
    def setAutoFetchIntervalMinutes(self, minutes: int) -> None:
        safe_minutes = max(1, min(int(minutes), 1440))
        self._configs.set("central_control.auto_fetch_interval_minutes", safe_minutes)
        self._configure_auto_fetch(fetch_immediately=False)
        self.changed.emit()

    @Slot(bool)
    def setAllowRemotePowerCommands(self, allowed: bool) -> None:
        self._configs.set("central_control.allow_remote_power_commands", allowed)
        self.changed.emit()

    @Slot(str, result=bool)
    def applyCentralSchedule(self, schedule_id: str) -> bool:
        """用户明确选择一个已校验并已缓存的集控课表后才切换。"""
        schedule = self._synced_schedules.get(str(schedule_id))
        if schedule is None:
            self._set_status(self.tr("未找到可应用的集控课程表"))
            return False
        local_name = str(schedule["localName"])
        if not self._schedule_manager.load(local_name, force=True):
            self._set_status(self.tr("无法切换到集控课程表“{0}”").format(schedule["name"]))
            return False
        self._last_applied_name = local_name
        self._set_status(self.tr("已手动切换到集控课程表“{0}”").format(schedule["name"]))
        self.applied.emit(local_name)
        return True

    @Slot()
    def fetchAndApplySchedule(self) -> None:
        if self._syncing:
            return

        manifest_url = self.manifestUrl.strip()
        if not manifest_url:
            self._set_status(self.tr("请先填写集控地址"))
            return
        if not manifest_url.startswith(("https://", "http://")):
            self._set_status(self.tr("集控地址必须以 http:// 或 https:// 开头"))
            return

        self._syncing = True
        self._status_before_sync = self._status_text
        self._set_status(self.tr("正在检查集控内容…"), emit=False)
        self.changed.emit()
        self._worker = _CentralControlFetchWorker(manifest_url, self)
        self._worker.completed.connect(self._on_fetch_completed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    @Slot(bool, str, object)
    def _on_fetch_completed(self, success: bool, error: str, payload: object) -> None:
        self._syncing = False
        if not success:
            if isinstance(payload, dict) and payload.get("silentlyRejected") is True:
                # 格式、哈希、架构或 yes.id 不合规时不接收、不通知，并保持上次状态。
                self._set_status(self._status_before_sync)
                return
            self._last_announcement_count = 0
            self._set_status(self.tr("集控内容接收失败：{0}").format(error))
            return

        self._last_announcement_count = 0

        try:
            schedule_count, policy_version, auto_applied_name, match_status = self._cache_schedules(payload)
            announcement_count, executed_power_action = self._apply_commands(payload)
        except Exception as exc:
            logger.exception("Failed to apply central-control content")
            self._set_status(self.tr("集控内容应用失败：{0}").format(exc))
            return

        self._last_applied_name = auto_applied_name
        self._last_policy_version = policy_version
        self._last_announcement_count = announcement_count
        self._last_match_status = match_status
        if auto_applied_name:
            status = self.tr("已同步 {0} 份集控课程表，并按唯一 yes.id=1 参数切换到“{1}”（策略版本：{2}）").format(
                schedule_count, auto_applied_name, policy_version
            )
            self.applied.emit(auto_applied_name)
        else:
            status = self.tr("已同步 {0} 份集控课程表；当前课程表未自动切换（策略版本：{1}；{2}）").format(
                schedule_count, policy_version, match_status
            )
        if announcement_count:
            status += self.tr("；已处理 {0} 条公告命令").format(announcement_count)
        if executed_power_action:
            status += self.tr("；已执行集控{0}命令").format(self._power_action_display(executed_power_action))
        self._set_status(status)

    @staticmethod
    def fetch_manifest_payload(manifest_url: str) -> dict:
        """下载并校验清单中的所有课程表和一次性公告命令。"""
        manifest_response = requests.get(
            manifest_url,
            timeout=15,
            headers={"Accept": "application/json", "User-Agent": "ClassWidgetsCentralControl/2"},
        )
        manifest_response.raise_for_status()
        manifest = manifest_response.json()
        if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
            raise ValueError("集控清单格式或版本不受支持")

        raw_schedules = manifest.get("schedules")
        if raw_schedules is None:
            # 兼容 schemaVersion 1 的旧单课表清单。
            raw_schedule = manifest.get("schedule")
            raw_schedules = [raw_schedule] if raw_schedule is not None else []
        if not isinstance(raw_schedules, list) or not raw_schedules:
            raise ValueError("集控清单缺少课程表信息")
        if len(raw_schedules) > MAX_SCHEDULES:
            raise ValueError(f"集控课程表数量不能超过 {MAX_SCHEDULES} 份")

        schedules: list[dict] = []
        schedule_ids: set[str] = set()
        for raw_schedule in raw_schedules:
            if not isinstance(raw_schedule, dict):
                raise ValueError("集控课程表信息格式无效")
            schedule_payload = CentralControlScheduleService._fetch_schedule_payload(manifest_url, raw_schedule)
            schedule_id = str(schedule_payload["id"])
            if schedule_id in schedule_ids:
                raise ValueError("集控课程表标识不能重复")
            schedule_ids.add(schedule_id)
            schedules.append(schedule_payload)

        return {
            "policy_version": str(manifest.get("policyVersion", "unknown")),
            "schedules": schedules,
            "commands": CentralControlScheduleService._validate_commands(manifest.get("commands", [])),
        }

    @staticmethod
    def _fetch_schedule_payload(manifest_url: str, schedule_info: dict) -> dict:
        schedule_id = str(schedule_info.get("id", ""))
        if not _SCHEDULE_ID_PATTERN.fullmatch(schedule_id):
            raise ValueError("课程表标识仅允许字母、数字、短横线和下划线")

        schedule_url = str(schedule_info.get("url", ""))
        expected_sha256 = str(schedule_info.get("sha256", "")).lower()
        if not schedule_url or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
            raise ValueError("集控清单缺少有效的课程表地址或 SHA-256 校验值")

        schedule_response = requests.get(
            urljoin(manifest_url, schedule_url),
            timeout=20,
            headers={"Accept": "application/json", "User-Agent": "ClassWidgetsCentralControl/2"},
        )
        schedule_response.raise_for_status()
        content = schedule_response.content
        if len(content) > MAX_SCHEDULE_BYTES:
            raise ValueError("课程表文件超过允许的 2 MB 大小")
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError("课程表 SHA-256 校验失败")

        try:
            schedule_raw = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("课程表不是有效的 UTF-8 JSON 文件") from exc
        schedule = ScheduleData.model_validate(schedule_raw)
        if schedule.meta.version != __SCHEDULE_SCHEMA_VERSION__:
            raise ValueError(f"不支持的课程表架构版本：{schedule.meta.version}")
        raw_yes = schedule_raw.get("yes", {})
        if raw_yes is None:
            raw_yes = {}
        if not isinstance(raw_yes, dict):
            raise ValueError("课程表 yes 参数必须是对象")
        yes_id = raw_yes.get("id", 0)
        if isinstance(yes_id, bool) or not isinstance(yes_id, int) or yes_id not in (0, 1):
            raise ValueError("课程表 yes.id 仅允许整数 0 或 1")
        return {
            "id": schedule_id,
            "name": str(schedule_info.get("name", schedule_id)),
            "schedule": schedule.model_dump(),
            "sha256": actual_sha256,
            "yesId": yes_id,
        }

    @staticmethod
    def _validate_commands(raw_commands: object) -> list[dict]:
        if raw_commands is None:
            return []
        if not isinstance(raw_commands, list):
            raise ValueError("集控命令必须是数组")
        if len(raw_commands) > MAX_COMMANDS:
            raise ValueError(f"集控命令数量不能超过 {MAX_COMMANDS} 条")

        commands: list[dict] = []
        power_command_count = 0
        for raw_command in raw_commands:
            if not isinstance(raw_command, dict):
                raise ValueError("集控命令格式无效")
            command_id = str(raw_command.get("id", ""))
            command_type = str(raw_command.get("type", ""))
            if not _COMMAND_ID_PATTERN.fullmatch(command_id):
                raise ValueError("集控命令标识格式无效")

            expires_at = raw_command.get("expiresAt")
            if expires_at is not None:
                if not isinstance(expires_at, str):
                    raise ValueError("集控命令过期时间无效")
                try:
                    datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError("集控命令过期时间必须是 ISO 8601 格式") from exc

            if command_type == "announcement":
                title = str(raw_command.get("title", "集控公告")).strip()
                message = str(raw_command.get("message", "")).strip()
                if not title or not message:
                    raise ValueError("公告命令必须包含标题和内容")
                if len(title) > 80 or len(message) > MAX_COMMAND_TEXT_LENGTH:
                    raise ValueError("公告标题或内容过长")
                try:
                    duration = int(raw_command.get("duration", 8000))
                except (TypeError, ValueError) as exc:
                    raise ValueError("公告显示时长无效") from exc
                commands.append(
                    {
                        "id": command_id,
                        "type": command_type,
                        "title": title,
                        "message": message,
                        "duration": max(1000, min(duration, 60000)),
                        "expiresAt": expires_at,
                    }
                )
                continue

            if command_type != "power":
                raise ValueError(f"不支持的集控命令类型：{command_type}")
            power_command_count += 1
            if power_command_count > 1:
                raise ValueError("一次集控下发最多包含 1 条电源命令")
            action = raw_command.get("action")
            if not isinstance(action, str) or action not in _POWER_COMMAND_TYPES:
                raise ValueError("集控电源命令动作无效")
            if expires_at is None:
                raise ValueError("集控电源命令必须包含过期时间")
            commands.append(
                {
                    "id": command_id,
                    "type": command_type,
                    "action": action,
                    "expiresAt": expires_at,
                }
            )
        return commands

    def _cache_schedules(self, payload: object) -> tuple[int, str, str, str]:
        """缓存所有已校验课表；仅在唯一一份课程表声明 yes.id=1 时才自动切换。"""
        if not isinstance(payload, dict):
            raise ValueError("课程表接收结果无效")
        raw_schedules = payload.get("schedules")
        if not isinstance(raw_schedules, list) or not raw_schedules:
            raise ValueError("课程表接收结果缺少课程表")

        synchronized: dict[str, dict] = {}
        for raw_schedule in raw_schedules:
            if not isinstance(raw_schedule, dict):
                raise ValueError("课程表接收结果格式无效")
            schedule_id = str(raw_schedule["id"])
            schedule = ScheduleData.model_validate(raw_schedule["schedule"])
            local_name = f"central_{schedule_id}"
            destination = self._schedule_manager.schedules_dir / f"{local_name}.json"
            temporary = destination.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(schedule.model_dump(), ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
            temporary.replace(destination)
            synchronized[schedule_id] = {
                "id": schedule_id,
                "name": str(raw_schedule.get("name", schedule_id)),
                "localName": local_name,
                "sha256": str(raw_schedule.get("sha256", "")),
                "yesId": int(raw_schedule.get("yesId", 0)),
            }

        self._synced_schedules = synchronized
        policy_version = str(payload.get("policy_version", "unknown"))
        matches = [schedule for schedule in synchronized.values() if schedule["yesId"] == 1]
        if not matches:
            return len(synchronized), policy_version, "", self.tr("没有课表声明 yes.id=1")
        if len(matches) > 1:
            return (
                len(synchronized),
                policy_version,
                "",
                self.tr("有 {0} 份课表声明 yes.id=1，已拒绝自动切换").format(len(matches)),
            )

        matched = matches[0]
        local_name = str(matched["localName"])
        if not self._schedule_manager.load(local_name, force=True):
            raise ValueError("无法切换到唯一匹配的集控课程表")
        return len(synchronized), policy_version, local_name, self.tr("唯一课表声明 yes.id=1")

    def _apply_commands(self, payload: object) -> tuple[int, str]:
        if not isinstance(payload, dict):
            raise ValueError("集控命令接收结果无效")

        commands = payload.get("commands", [])
        if not isinstance(commands, list):
            raise ValueError("集控命令接收结果无效")

        completed_ids = list(self._configs.central_control.executed_command_ids)
        completed_id_set = set(completed_ids)
        completed_changed = False
        announcement_count = 0
        executed_power_action = ""
        for command in commands:
            command_id = command["id"]
            if command_id in completed_id_set or self._is_command_expired(command.get("expiresAt")):
                continue

            if command["type"] == "announcement":
                self._notification_provider.push(
                    int(NotificationLevel.ANNOUNCEMENT),
                    command["title"],
                    command["message"],
                    command["duration"],
                    True,
                )
                announcement_count += 1
            else:
                action = str(command["action"])
                if not self.allowRemotePowerCommands:
                    logger.info("Ignored remote power command because local authorization is disabled")
                else:
                    # 直接重启可能在普通的周期性配置保存前终止进程；先同步持久化 ID。
                    completed_ids.append(command_id)
                    completed_id_set.add(command_id)
                    if not self._persist_completed_command_ids(completed_ids):
                        logger.error("Refused remote power command because its completion ID could not be persisted")
                        return announcement_count, executed_power_action
                    completed_changed = False
                    if self._execute_power_command(action):
                        executed_power_action = action
                    continue

            completed_ids.append(command_id)
            completed_id_set.add(command_id)
            completed_changed = True

        if completed_changed:
            self._configs.set(
                "central_control.executed_command_ids",
                completed_ids[-MAX_EXECUTED_COMMAND_IDS:],
            )
        return announcement_count, executed_power_action

    def _persist_completed_command_ids(self, completed_ids: list[str]) -> bool:
        persisted_ids = completed_ids[-MAX_EXECUTED_COMMAND_IDS:]
        self._configs.set("central_control.executed_command_ids", persisted_ids)
        if list(self._configs.central_control.executed_command_ids) != persisted_ids:
            return False
        save = getattr(self._configs, "save", None)
        if callable(save):
            try:
                save(silent=True)
            except Exception:
                logger.exception("Failed to save completed central-control command IDs")
                return False
        return True

    def _execute_power_command(self, action: str) -> bool:
        try:
            command = self._power_command_arguments(action)
            subprocess.Popen(command, close_fds=True)
        except (OSError, ValueError):
            logger.exception("Failed to execute remote power command")
            return False
        return True

    @staticmethod
    def _power_command_arguments(action: str) -> list[str]:
        if sys.platform == "win32":
            commands = {
                "restart": ["shutdown", "/r", "/t", "0"],
                "shutdown": ["shutdown", "/s", "/t", "0"],
                "hibernate": ["shutdown", "/h"],
                "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            }
        elif sys.platform == "darwin":
            commands = {
                "restart": ["/sbin/shutdown", "-r", "now"],
                "shutdown": ["/sbin/shutdown", "-h", "now"],
                "hibernate": ["pmset", "sleepnow"],
                "sleep": ["pmset", "sleepnow"],
            }
        elif sys.platform.startswith("linux"):
            commands = {
                "restart": ["systemctl", "reboot"],
                "shutdown": ["systemctl", "poweroff"],
                "hibernate": ["systemctl", "hibernate"],
                "sleep": ["systemctl", "suspend"],
            }
        else:
            raise ValueError("当前系统不支持集控电源命令")
        return commands[action]

    def _power_action_display(self, action: str) -> str:
        return {
            "restart": self.tr("重启"),
            "shutdown": self.tr("关机"),
            "hibernate": self.tr("休眠"),
            "sleep": self.tr("睡眠"),
        }.get(action, self.tr("电源"))

    @staticmethod
    def _is_command_expired(expires_at: object) -> bool:
        if not expires_at:
            return False
        try:
            expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            return True
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires.astimezone(timezone.utc) <= datetime.now(timezone.utc)

    def _configure_auto_fetch(self, fetch_immediately: bool) -> None:
        self._auto_fetch_timer.stop()
        if not self.autoFetchEnabled or not self.manifestUrl.strip():
            return

        interval_ms = self.autoFetchIntervalMinutes * 60 * 1000
        self._auto_fetch_timer.setInterval(interval_ms)
        self._auto_fetch_timer.start()
        if fetch_immediately:
            QTimer.singleShot(0, self.fetchAndApplySchedule)

    def _set_status(self, status_text: str, emit: bool = True) -> None:
        self._status_text = status_text
        if emit:
            self.changed.emit()
