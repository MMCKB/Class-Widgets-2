import sys
import os

# Add the project root to Python path (parent directory of src)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from src.core import AppCentral
from PySide6.QtWidgets import QApplication


def _detect_cwplugin_arg(argv: list[str]) -> tuple[str | None, list[str]]:
    """从启动参数中检测 .cwplugin 文件路径，返回 (路径, 剩余参数)。

    Windows 文件关联传参时，含空格的路径会被引号包裹，需先去除引号再判断。
    """
    pending: str | None = None
    rest: list[str] = []
    for arg in argv:
        stripped = arg.strip('"').strip("'")
        if pending is None and stripped.lower().endswith(".cwplugin") and os.path.isfile(stripped):
            pending = stripped
        else:
            rest.append(arg)
    return pending, rest


if __name__ == "__main__":
    standalone_modes = {
        "--settings-only": "settings",
        "--plugin-plaza-only": "plaza",
        "--settings-plaza": "both",  # 兼容旧的组合启动参数
    }

    # 检测 .cwplugin 文件：用户双击插件文件启动时，路径会出现在参数里
    pending_plugin, remaining_args = _detect_cwplugin_arg(sys.argv[1:])
    if pending_plugin:
        sys.argv = [sys.argv[0]] + remaining_args

    selected_mode = next(
        (standalone_modes[arg] for arg in sys.argv[1:] if arg in standalone_modes),
        None,
    )
    if selected_mode:
        # 包内独立入口会调用此模式；不加载桌面 Widget 窗口。
        sys.argv = [arg for arg in sys.argv if arg not in standalone_modes]
        from src.settings_plaza_app import main as settings_plaza_main

        raise SystemExit(settings_plaza_main(selected_mode, pending_plugin=pending_plugin))

    app = QApplication(sys.argv)
    instance = AppCentral(pending_plugin=pending_plugin)
    instance.run()
    app.exec()
