"""
AMS2 Memory Map Control for accessing AMS2 Shared Memory Interface
"""

from __future__ import annotations

import ctypes
import logging
import mmap
import platform

from ._common import get_root_logger_name
from .ams2_data import AMS2Constants

logger = logging.getLogger(get_root_logger_name())


def platform_mmap(name: str, size: int) -> mmap.mmap:
    """Platform memory mapping"""
    if platform.system() == "Windows":
        return windows_mmap(name, size)
    return linux_mmap(name, size)


def windows_mmap(name: str, size: int) -> mmap.mmap:
    """Windows mmap"""
    return mmap.mmap(-1, size, name)


def linux_mmap(name: str, size: int) -> mmap.mmap:
    """Linux mmap - read data from '/dev/shm/filename'

    The file is owned by the game (or its Wine/Proton bridge), so it is never
    created here: creating it would leave a wrongly laid out file behind, which
    other readers (SimHub, CrewChief, etc) would then pick up.

    Raises:
        FileNotFoundError: file does not exist yet (game not running).
        ValueError: file is smaller than `size` (not fully set up yet).
    """
    # "r+b" opens existing file read/write without creating it
    with open("/dev/shm/" + name, "r+b") as file:
        return mmap.mmap(file.fileno(), size)


class MMapControl:
    """Memory map control"""

    __slots__ = (
        "_buffer",
        "_mmap_buffer",
        "_mmap_name",
        "_realtime",
        "_struct",
        "data",
        "update",
    )

    def __init__(self, mmap_name: str, data_struct: ctypes.Structure) -> None:
        """Initialize memory map setting

        Args:
            mmap_name: mmap filename.
            data_struct: ctypes data structure, ex. ams2_data.SharedMemory.
        """
        self._buffer = bytearray()
        self._mmap_buffer = None
        self._mmap_name = mmap_name
        self._struct = data_struct
        self._realtime = None
        self.update = None
        self.data = None

    def __del__(self):
        logger.info("sharedmemory: GC: MMap %s", self._mmap_name)

    def create(self, access_mode: int = 0) -> None:
        """Create mmap instance & initial accessible copy

        Args:
            access_mode: 0 = copy access, 1 = direct access.
        """
        self._mmap_buffer = platform_mmap(
            name=self._mmap_name,
            size=ctypes.sizeof(self._struct),
        )

        if access_mode:
            self.data = self._struct.from_buffer(self._mmap_buffer)
            self.update = self.__buffer_share
        else:
            self._buffer[:] = self._mmap_buffer
            self._realtime = self._struct.from_buffer(self._mmap_buffer)
            self.data = self._struct.from_buffer(self._buffer)
            self.update = self.__buffer_sequence

        mode = "Direct" if access_mode else "Copy"
        logger.info("sharedmemory: ACTIVE: %s (%s Access)", self._mmap_name, mode)

    def close(self) -> None:
        """Close memory mapping

        Create a final accessible mmap data copy before closing mmap instance.
        """
        self.data = self._struct.from_buffer_copy(self._mmap_buffer)
        self._realtime = None
        try:
            self._mmap_buffer.close()
            logger.info("sharedmemory: CLOSED: %s", self._mmap_name)
        except BufferError:
            logger.error("sharedmemory: buffer error while closing %s", self._mmap_name)
        self.update = None  # unassign update method (for proper garbage collection)

    def __buffer_share(self) -> None:
        """Share buffer access, may result data desync"""

    def __buffer_sequence(self) -> None:
        """Copy buffer access, helps avoid data desync

        AMS2 increments sequence number at start & end of each write cycle:
        odd = data being written, even = data stable. Skip while odd, and
        re-copy once if sequence changed during copy (torn data).
        """
        sequence = self._realtime.mSequenceNumber
        if sequence % 2:  # game is writing data, skip this update
            return
        self._buffer[:] = self._mmap_buffer
        if self._realtime.mSequenceNumber != sequence:  # changed during copy
            sequence = self._realtime.mSequenceNumber
            if not sequence % 2:  # retry only if data is stable
                self._buffer[:] = self._mmap_buffer
