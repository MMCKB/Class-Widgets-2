# 插件自动化扩展开发指南

ClassWidgets 允许插件在“设置 → 自动化”中接入三类受控能力：**插件自动化项目**、**插件触发器**与**插件行动**。项目用于展示独立开关和设置入口；触发器与行动会作为用户创建本地自动化规则时的可选项出现。

> 所有插件扩展都在本地进程内运行。插件只能发出自己已注册的触发器，且插件行动只有在用户明确选择、保存并启用相应本地规则后才会执行。

## 能力概览

| 能力 | 支持情况 |
|---|---|
| 在自动化页面显示插件项目卡片 | 支持。 |
| 用户单独启用或停用插件项目 | 支持，开关状态会持久化。 |
| 从项目卡片打开插件设置 | 支持。 |
| 在规则“当……”中加入插件触发器 | 支持。 |
| 在规则行动列表中加入插件行动 | 支持。 |
| 插件主动发出自身注册的触发器 | 支持。 |
| 命中规则时调用插件本地回调 | 支持。 |
| 远程下发 Shell 命令、远程重启或硬件控制 | 支持。 |

## 快速开始

插件应在 `on_load()`（并先调用 `super().on_load()`）后注册能力。插件提供的本地 ID 会自动加上插件 ID 命名空间。

```python
from src.core.plugin import CW2Plugin


class FocusPlugin(CW2Plugin):
    def on_load(self):
        super().on_load()

        self.project_id = self.api.automation.register_project(
            project_id="focus-mode",
            title="专注模式",
            description="用户可单独启用专注模式能力。",
            icon="ic_fluent_leaf_three_20_regular",
            on_enabled_changed=self.on_project_enabled,
            on_open_settings=self.open_settings,
        )

        self.trigger_id = self.api.automation.register_trigger(
            trigger_id="focus-started",
            title="插件专注已开始",
            description="由本插件开始专注计时后发出。",
            icon="ic_fluent_timer_20_regular",
        )

        self.action_id = self.api.automation.register_action(
            action_id="record-focus",
            title="记录专注开始",
            description="规则命中时由插件记录一次本地专注事件。",
            on_execute=self.record_focus,
            icon="ic_fluent_note_add_20_regular",
        )

    def on_project_enabled(self, enabled: bool) -> None:
        if enabled:
            self.start_focus_support()
        else:
            self.stop_focus_support()

    def on_focus_started(self) -> None:
        # 只会匹配用户已启用的本地规则。
        self.api.automation.emit_trigger(self.trigger_id)

    def record_focus(self, context: dict) -> bool:
        # context 包含 profile、rule 与 action 的本地配置快照。
        self.write_local_focus_record(context["rule"]["name"])
        return True

    def open_settings(self) -> None:
        self.show_settings_window()

    def on_unload(self) -> None:
        self.stop_focus_support()
```

示例中返回的全局 ID 分别类似：

```text
org.example.focus.focus-mode
plugin.org.example.focus.focus-started
plugin.org.example.focus.record-focus
```

`org.example.focus` 是插件元数据中的 ID。插件项目 ID 使用项目命名空间；触发器和行动 ID 使用 `plugin.` 前缀，以免和内置自动化类型冲突。

## 用户配置流程

插件注册后，用户在“设置 → 自动化”中创建或编辑本地配置文件和规则。用户可以在“当”的下拉列表中选择插件触发器，在“执行以下动作”的下拉列表中选择插件行动；规则、冷却时间与配置文件开关仍完全由用户控制。

插件行动不在 CW 页面中提供任意参数输入框。需要参数的插件应使用自己的设置页保存参数，并在 `on_execute(context)` 中读取自身本地设置。这样不会把插件私有配置、凭据或敏感数据写入 CW 自动化规则文件。

## API 参考

### `register_project`

```python
self.api.automation.register_project(
    project_id: str,
    title: str,
    description: str = "",
    icon: str = "ic_fluent_plug_connected_20_regular",
    on_enabled_changed: Callable[[bool], object] | None = None,
    on_open_settings: Callable[[], object] | None = None,
) -> str
```

项目用于展示插件独立能力。用户保存的项目开关存储于本地 `automation_plugin_projects.json`，不包含插件的业务设置或敏感数据。

### `register_trigger`

```python
self.api.automation.register_trigger(
    trigger_id: str,
    title: str,
    description: str = "",
    icon: str = "ic_fluent_plug_connected_20_regular",
) -> str
```

注册后，触发器会出现在自动化规则的“当”选项中。`trigger_id` 只能包含字母、数字、`.`、`_` 和 `-`，最长 80 个字符。它必须由插件随后通过 `emit_trigger()` 主动发出。

### `emit_trigger`

```python
self.api.automation.emit_trigger(trigger_id: str) -> bool
```

推荐传入 `register_trigger()` 返回的全局 ID，例如 `plugin.org.example.focus.focus-started`；这样插件在生命周期回调之外也能可靠发出自身事件。CW 仅对用户启用的配置文件与规则执行匹配，冷却时间继续生效。触发器不存在或插件已卸载时返回 `False`。

### `register_action`

```python
self.api.automation.register_action(
    action_id: str,
    title: str,
    on_execute: Callable[[dict], object],
    description: str = "",
    icon: str = "ic_fluent_plug_connected_20_regular",
) -> str
```

注册后，行动会出现在规则行动下拉列表中。命中规则时，CW 在本地调用 `on_execute(context)`；`context` 中含有 `profile`、`rule` 和 `action` 的配置快照。回调返回 `False` 表示该行动失败，其他返回值（包括 `None`）视为成功。

## 生命周期与卸载

| 生命周期事件 | CW 行为 | 插件应做的事 |
|---|---|---|
| 插件加载并注册项目 | 恢复已保存项目开关并调用 `on_enabled_changed`。 | 根据回调启动或停止自身能力。 |
| 插件注册触发器/行动 | 自动刷新自动化设置页选项。 | 仅注册稳定的本地 ID。 |
| 插件调用 `emit_trigger()` | 仅运行用户启用且匹配的规则。 | 不要假定必然有规则或行动执行。 |
| 用户命中插件行动 | 调用 `on_execute(context)`。 | 快速返回；耗时工作应自行交给可取消的任务。 |
| 插件卸载或替换 | 移除项目、触发器和行动的运行时注册；历史规则文件不会被删除。 | 停止线程、定时器、监听器和其他后台工作。 |
| 已卸载插件对应的历史规则 | 不会调用失效插件代码；失效插件行动会被安全跳过。 | 重新安装同 ID 插件后再由用户检查规则。 |

## 安全边界

插件触发器和行动不是远程执行通道，也不授予额外系统权限。

- 插件只能发出本插件已注册的触发器，不能伪造其他插件或内置事件。
- 插件行动只会在用户明确选择、保存并启用的本地规则命中后调用。
- CW 不为插件提供远程 Shell、远程重启、硬件控制、集控下发或绕过用户确认的接口。
- 插件行动回调在本地进程内执行；插件应自行处理网络、文件、进程或设备权限，并在自身设置页明确告知用户用途。
- 插件卸载后其行动回调会立即从运行时注册表移除，已保存规则不会保留可执行回调。
- 插件项目开关仍仅保存在本机；不会同步到集控。

## 常见问题

### 触发器或行动没有出现在自动化页面

确认在 `on_load()` 或其后注册，并且先调用了 `super().on_load()`。只有有效插件上下文才能自动取得插件 ID；注册成功后自动化页面会刷新选项。

### 为什么发出触发器后没有执行行动

检查对应配置文件与规则是否启用、规则是否选择了正确触发器、是否仍处于冷却时间，以及插件行动是否仍由已加载插件注册。插件触发器本身不会绕过这些用户配置。

### 可以在行动回调中直接执行耗时操作吗

不建议。行动回调发生在自动化服务调用路径中。耗时计算、网络请求或阻塞式 I/O 应由插件转交给自身可取消的工作线程或异步任务；卸载时必须停止这些任务。
