"""
Common
"""

from __future__ import annotations

import ctypes
import enum
import logging
from typing import Callable, Iterable


# Function
# Game (Windows) uses 2-byte UTF-16 wchar_t for strings in shared memory.
# ctypes.c_wchar matches that on Windows, but is 4-byte (UTF-32) on Linux/macOS,
# which changes struct size & field offsets. Where wchar_t is not 2 bytes,
# wide string fields are mapped as uint16 arrays and decoded via property instead.
WCHAR_IS_UTF16: bool = ctypes.sizeof(ctypes.c_wchar) == 2


def _is_wchar_array(ctype) -> bool:
    """Is ctypes array of c_wchar"""
    return getattr(ctype, "_type_", None) is ctypes.c_wchar and hasattr(ctype, "_length_")


def _utf16_property(raw_name: str, length: int) -> property:
    """Property that reads/writes a UTF-16LE (Windows wchar_t) char array as str"""

    def getter(self) -> str:
        text = bytes(getattr(self, raw_name)).decode("utf-16-le", errors="ignore")
        return text.split("\x00", 1)[0]

    def setter(self, value: str) -> None:
        data = str(value).encode("utf-16-le")[: (length - 1) * 2].ljust(length * 2, b"\x00")
        setattr(self, raw_name, (ctypes.c_uint16 * length).from_buffer_copy(data))

    return property(getter, setter)


def typedstruct(cls=None, pack=None):
    """Generate typed struct"""

    def wrap(cls):
        if not hasattr(cls, "__annotations__"):
            raise TypeError("missing __annotations__")
        # Add _pack_
        if pack is not None:
            cls._pack_ = pack
        # Add _fields_
        fields = []
        wide_fields = []
        for name in cls.__annotations__:
            ctype = cls.__dict__[name]
            if not WCHAR_IS_UTF16 and _is_wchar_array(ctype):
                raw_name = f"_raw_{name}"
                fields.append((raw_name, ctypes.c_uint16 * ctype._length_))
                wide_fields.append((name, raw_name, ctype._length_))
            else:
                fields.append((name, ctype))
        cls._fields_ = fields
        for name, raw_name, length in wide_fields:
            setattr(cls, name, _utf16_property(raw_name, length))
        return cls

    if cls is None:
        return wrap
    return wrap(cls)


def _t(v):
    """Wrapper for type"""
    return v


def enum_map(reference: Iterable[enum.Enum], default: str = "Unknown") -> Callable[[int], str]:
    """Generate lookup mapping from enum (class)"""
    func = {d.value: d.name for d in reference}.get
    return lambda index: func(index, default)


def dict_map(data: dict, default: str = "Unknown") -> Callable[[int], str]:
    """Generate lookup mapping from dict (class)"""
    func = data.get
    return lambda index: func(index, default)


def get_root_logger_name():
    """Get root logger name"""
    for logger_name in logging.root.manager.loggerDict:
        return logger_name
    return __name__
