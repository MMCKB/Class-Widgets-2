"""Windows 系统主音量控制。"""

from __future__ import annotations

import ctypes
import sys
from ctypes import POINTER, Structure, byref, c_int, c_long, c_ulong, c_void_p, wintypes

from loguru import logger


class _Guid(Structure):
    _fields_ = (
        ("Data1", c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    )

    @classmethod
    def from_string(cls, value: str) -> "_Guid":
        parts = value.strip("{}").split("-")
        return cls(
            int(parts[0], 16),
            int(parts[1], 16),
            int(parts[2], 16),
            (ctypes.c_ubyte * 8)(*(int(f"{parts[3]}{parts[4]}"[index : index + 2], 16) for index in range(0, 16, 2))),
        )


_CLSID_MMDEVICE_ENUMERATOR = _Guid.from_string("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
_IID_IMMDEVICE_ENUMERATOR = _Guid.from_string("{A95664D2-9614-4B35-A746-DE8DB63617E6}")
_IID_IAUDIO_ENDPOINT_VOLUME = _Guid.from_string("{5CDF2C82-841E-4546-9722-0CF74078229A}")

_CLSCTX_ALL = 23
_COINIT_APARTMENTTHREADED = 0x2
_ERENDER = 0
_ECONSOLE = 0


def _release(interface: c_void_p) -> None:
    if not interface:
        return
    vtable = ctypes.cast(interface, POINTER(POINTER(c_void_p))).contents
    release = ctypes.WINFUNCTYPE(c_ulong, c_void_p)(vtable[2])
    release(interface)


def _succeeded(result: int) -> bool:
    return result >= 0


def set_system_volume(percent: int) -> bool:
    """将 Windows 默认输出设备的主音量设置为 0–100；非 Windows 平台安全跳过。"""
    if sys.platform != "win32":
        logger.info("System volume control is only available on Windows")
        return False

    normalized_percent = max(0, min(100, int(percent)))
    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = (c_void_p, c_ulong)
    ole32.CoInitializeEx.restype = c_long
    ole32.CoCreateInstance.argtypes = (POINTER(_Guid), c_void_p, c_ulong, POINTER(_Guid), POINTER(c_void_p))
    ole32.CoCreateInstance.restype = c_long
    ole32.CoUninitialize.argtypes = ()
    ole32.CoUninitialize.restype = None
    initialized = False
    enumerator = c_void_p()
    device = c_void_p()
    endpoint_volume = c_void_p()

    try:
        result = ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
        if not _succeeded(result):
            logger.warning("Could not initialize COM for system volume control: {}", result)
            return False
        initialized = True

        result = ole32.CoCreateInstance(
            byref(_CLSID_MMDEVICE_ENUMERATOR),
            None,
            _CLSCTX_ALL,
            byref(_IID_IMMDEVICE_ENUMERATOR),
            byref(enumerator),
        )
        if not _succeeded(result):
            logger.warning("Could not create Windows audio device enumerator: {}", result)
            return False

        enumerator_vtable = ctypes.cast(enumerator, POINTER(POINTER(c_void_p))).contents
        get_default_endpoint = ctypes.WINFUNCTYPE(c_long, c_void_p, c_int, c_int, POINTER(c_void_p))(
            enumerator_vtable[4]
        )
        result = get_default_endpoint(enumerator, _ERENDER, _ECONSOLE, byref(device))
        if not _succeeded(result):
            logger.warning("Could not find the default Windows output device: {}", result)
            return False

        device_vtable = ctypes.cast(device, POINTER(POINTER(c_void_p))).contents
        activate = ctypes.WINFUNCTYPE(c_long, c_void_p, POINTER(_Guid), c_ulong, c_void_p, POINTER(c_void_p))(
            device_vtable[3]
        )
        result = activate(device, byref(_IID_IAUDIO_ENDPOINT_VOLUME), _CLSCTX_ALL, None, byref(endpoint_volume))
        if not _succeeded(result):
            logger.warning("Could not access default Windows output volume: {}", result)
            return False

        endpoint_vtable = ctypes.cast(endpoint_volume, POINTER(POINTER(c_void_p))).contents
        set_master_volume = ctypes.WINFUNCTYPE(c_long, c_void_p, ctypes.c_float, c_void_p)(endpoint_vtable[7])
        result = set_master_volume(endpoint_volume, normalized_percent / 100, None)
        if not _succeeded(result):
            logger.warning("Could not set Windows system volume: {}", result)
            return False

        logger.info("Set Windows system volume to {}%", normalized_percent)
        return True
    except OSError as error:
        logger.warning("Windows system volume control failed: {}", error)
        return False
    finally:
        _release(endpoint_volume)
        _release(device)
        _release(enumerator)
        if initialized:
            ole32.CoUninitialize()
