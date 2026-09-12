import multiprocessing
import os
import sys
import time


def wait_for_process_exit(arguments: list[str]) -> list[str]:
    """Wait for the previous CW2 process before initializing Qt and plugins."""
    if "--wait-for-pid" not in arguments:
        return arguments

    index = arguments.index("--wait-for-pid")
    try:
        pid = int(arguments[index + 1])
    except (IndexError, ValueError):
        return arguments[:index] + arguments[index + 2:]

    remaining = arguments[:index] + arguments[index + 2:]
    if pid == os.getpid():
        return remaining

    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return remaining
        except PermissionError:
            pass
        time.sleep(0.1)

# Add the project root to Python path (parent directory of src)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from src.core import AppCentral
from PySide6.QtWidgets import QApplication


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.argv[1:] = wait_for_process_exit(sys.argv[1:])

    standalone_modes = {
        "--settings-only": "settings",
        "--plugin-plaza-only": "plaza",
        "--settings-plaza": "both",  # 兼容旧的组合启动参数
    }
    selected_mode = next(
        (standalone_modes[arg] for arg in sys.argv[1:] if arg in standalone_modes),
        None,
    )
    if selected_mode:
        # 包内独立入口会调用此模式；不加载桌面 Widget 窗口。
        sys.argv = [arg for arg in sys.argv if arg not in standalone_modes]
        from src.settings_plaza_app import main as settings_plaza_main

        raise SystemExit(settings_plaza_main(selected_mode))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    instance = AppCentral()
    instance.run()
    app.exec()
