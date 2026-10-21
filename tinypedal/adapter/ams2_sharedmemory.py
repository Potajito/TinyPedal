#  TinyPedal is an open-source overlay application for racing simulation.
#  Copyright (C) 2022-2026 TinyPedal developers, see contributors.md file
#
#  This file is part of TinyPedal.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
AMS2 sharedmemory API connector
"""

from __future__ import annotations

import ctypes
import logging
import threading
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # for type checker only
    from thirdparty.pyAMS2SharedMemory import ams2_data
    from thirdparty.pyAMS2SharedMemory.ams2_data import AMS2Constants
    from thirdparty.pyAMS2SharedMemory.ams2_mmap import MMapControl
else:  # run time only
    from pyAMS2SharedMemory import ams2_data
    from pyAMS2SharedMemory.ams2_data import AMS2Constants
    from pyAMS2SharedMemory.ams2_mmap import MMapControl

from ..process.timing import LastSectorTime, ValidLapStatus
from ..process.vehicle import LastImpact

logger = logging.getLogger(__name__)

# Constant & Enum
INVALID_INDEX = AMS2Constants.INVALID_PARTICIPANT_INDEX

# Game states considered active while driving
ACTIVE_GAME_STATES = (
    ams2_data.GameState.GAME_INGAME_PLAYING,
    ams2_data.GameState.GAME_INGAME_INMENU_TIME_TICKING,
)


def copy_struct(struct_data):
    """Allow to copy ctypes struct data with __slots__"""
    return type(struct_data).from_buffer_copy(
        ctypes.string_at(
            ctypes.byref(struct_data),
            ctypes.sizeof(struct_data),
        )
    )


class MMapDataSet:
    """Create mmap data set"""

    __slots__ = (
        "shmm",
    )

    def __init__(self) -> None:
        self.shmm = MMapControl(AMS2Constants.MM_SHARED_MEMORY_NAME, ams2_data.SharedMemory)

    def __del__(self):
        logger.info("sharedmemory: GC: MMapDataSet")

    def create_mmap(self, access_mode: int) -> None:
        """Create mmap instance

        Args:
            access_mode: 0 = copy access, 1 = direct access.
        """
        self.shmm.create(access_mode)

    def close_mmap(self) -> None:
        """Close mmap instance"""
        self.shmm.close()

    def update_mmap(self) -> None:
        """Update mmap data"""
        self.shmm.update()


class SyncData:
    """Synchronize data with viewed participant index

    Attributes:
        dataset: mmap data set.
        paused: Is API data paused.
        synced: Is player data synced.
        resets: Number of player vehicle resets.
        override_player_index: Is player index overridden.
        player_index: Overridden player index.
        player_shmm: Player shared memory data.
        player_index_resolved: Local player participant index.
    """

    __slots__ = (
        "_updating",
        "_mapped",
        "_update_thread",
        "_event",
        "paused",
        "synced",
        "resets",
        "override_player_index",
        "player_index",
        "player_shmm",
        "player_index_resolved",
        "dataset",
        "elapsed_time",
    )

    def __init__(self) -> None:
        self._updating = False
        self._mapped = False
        self._update_thread = None
        self._event = threading.Event()

        self.paused = False
        self.synced = False
        self.resets = 0
        self.override_player_index = False
        self.player_index = INVALID_INDEX
        self.player_shmm: ams2_data.SharedMemory = None
        self.player_index_resolved = INVALID_INDEX
        self.dataset = MMapDataSet()
        self.elapsed_time = 0.0

    def __del__(self):
        logger.info("sharedmemory: GC: SyncData")

    def start(self, access_mode: int) -> None:
        """Update & sync mmap data copy in separate thread

        Args:
            access_mode: 0 = copy access, 1 = direct access.
        """
        if self._updating:
            logger.warning("sharedmemory: UPDATING: already started")
        else:
            self._updating = True
            # Use blank data until mmap is available
            self.player_shmm = ams2_data.SharedMemory()
            # Initialize mmap data, if game is not running yet, keep waiting in thread
            self._mapped = False
            if not self.__map_dataset(access_mode):
                logger.info("sharedmemory: WAITING: shared memory not available yet")
            # Setup updating thread
            self._event.clear()
            self._update_thread = threading.Thread(
                target=self.__update, args=(access_mode,), daemon=True
            )
            self._update_thread.start()
            logger.info("sharedmemory: UPDATING: thread started")
            logger.info("sharedmemory: player index override: %s", self.override_player_index)

    def stop(self) -> None:
        """Join and stop updating thread, close mmap"""
        if self._updating:
            self._event.set()
            self._updating = False
            self._update_thread.join()
            # Make final copy before close, otherwise mmap won't close if using direct access
            self.player_shmm = copy_struct(self.player_shmm)
            if self._mapped:
                self.dataset.close_mmap()
                self._mapped = False
        else:
            logger.warning("sharedmemory: UPDATING: already stopped")

    def __map_dataset(self, access_mode: int) -> bool:
        """Try creating mmap data set, without creating any shared memory file

        Returns:
            True if mmap is ready, False if game has not provided shared memory yet.
        """
        try:
            self.dataset.create_mmap(access_mode)
        except (FileNotFoundError, ValueError, PermissionError):
            return False
        self.player_shmm = self.dataset.shmm.data
        self._mapped = True
        version = self.player_shmm.mVersion
        if version != AMS2Constants.SHARED_MEMORY_VERSION:
            logger.warning(
                "sharedmemory: data version mismatch, expected %s, got %s",
                AMS2Constants.SHARED_MEMORY_VERSION, version,
            )
        return True

    def __update(self, access_mode: int) -> None:
        """Update synced player data"""
        self.paused = True
        self.synced = False
        self.resets = 0

        _event_wait = self._event.wait

        # Wait for game (or its bridge) to provide shared memory
        while not self._mapped:
            if _event_wait(1.0):  # stop requested
                logger.info("sharedmemory: UPDATING: thread stopped")
                return
            if self.__map_dataset(access_mode):
                logger.info("sharedmemory: UPDATING: shared memory found")

        freezed_timestamp = 0  # store freezed timestamp
        last_session_timestamp = 0  # store last timestamp
        last_update_time = 0.0
        data_freezed = True  # whether data is freezed

        last_odometer = 0.0
        last_track_name = b""
        reset_counter = 0
        update_delay = 0.5  # longer delay while inactive

        self.elapsed_time = 0.0
        session_timestamp = 0
        last_mono_time = 0.0

        while not _event_wait(update_delay):
            self.dataset.update_mmap()
            session_timestamp = self.player_shmm.mSequenceNumber

            # Update player data & index
            if not data_freezed:
                # Get player index
                if self.override_player_index:
                    player_index = self.player_index
                else:
                    player_index = self.player_shmm.mViewedParticipantIndex
                num_participants = min(
                    self.player_shmm.mNumParticipants, AMS2Constants.STORED_PARTICIPANTS_MAX
                )
                data_synced = 0 <= player_index < num_participants
                if data_synced:
                    self.player_index_resolved = player_index
                    reset_counter = 0
                    self.synced = True
                # Pause if local player index no longer exists, 5 tries
                elif reset_counter < 6:
                    reset_counter += 1
                    if reset_counter == 5:
                        self.player_index_resolved = INVALID_INDEX
                        self.synced = False
                        logger.info("sharedmemory: UPDATING: player data paused")

            if last_session_timestamp != session_timestamp:
                # Calculate delta & elapsed time
                mono_time = monotonic()
                # AMS2 keeps updating shared memory while paused, so exclude
                # paused state from elapsed time, otherwise lap validation
                # timers (ex. delta best) expire during pause
                if self.player_shmm.mGameState != ams2_data.GameState.GAME_INGAME_PAUSED:
                    self.elapsed_time += min(mono_time - last_mono_time, 0.1)
                last_mono_time = mono_time

                # Check resets
                odometer = self.player_shmm.mOdometerKM
                track_name = self.player_shmm.mTrackLocation
                if (
                    last_session_timestamp > session_timestamp  # session changed
                    or (odometer >= 0 and last_odometer > odometer)  # returned to garage
                    or last_track_name != track_name  # changed track
                ):
                    self.elapsed_time = 0.0
                    self.resets += 1

                last_update_time = monotonic()
                last_session_timestamp = session_timestamp
                last_odometer = odometer
                last_track_name = track_name

            if data_freezed:
                # Check while IN freeze state
                if freezed_timestamp != last_session_timestamp:
                    update_delay = 0.01
                    self.paused = data_freezed = False
                    logger.info(
                        "sharedmemory: UPDATING: resumed, data timestamp %s",
                        last_session_timestamp,
                    )
            # Check while NOT IN freeze state
            # Set freeze state if data stopped updating after 2s
            elif monotonic() - last_update_time > 2:
                update_delay = 0.5
                self.paused = data_freezed = True
                self.synced = False
                freezed_timestamp = last_session_timestamp
                logger.info(
                    "sharedmemory: UPDATING: paused, data timestamp %s",
                    freezed_timestamp,
                )

        logger.info("sharedmemory: UPDATING: thread stopped")


class AMS2Info:
    """AMS2 shared memory data output"""

    __slots__ = (
        "_sync",
        "_access_mode",
        "_state_override",
        "_active_state",
        "_last_impact",
        "_last_sector_time",
        "_valid_lap_status",
    )

    def __init__(self) -> None:
        self._sync = SyncData()
        self._access_mode = 0
        self._state_override = False
        self._active_state = False
        self._last_impact = LastImpact()
        self._last_sector_time = LastSectorTime()
        self._valid_lap_status = ValidLapStatus()

    def __del__(self):
        logger.info("sharedmemory: GC: AMS2Info")

    def start(self) -> None:
        """Start data updating thread"""
        self._sync.start(self._access_mode)

    def stop(self) -> None:
        """Stop data updating thread"""
        self._sync.stop()

    def setMode(self, mode: int = 0) -> None:
        """Set mmap access mode

        Args:
            mode: 0 = copy access, 1 = direct access
        """
        self._access_mode = mode

    def setStateOverride(self, state: bool = False) -> None:
        """Enable state override"""
        self._state_override = state

    def setActiveState(self, state: bool = False) -> None:
        """Set state override"""
        self._active_state = state

    def setPlayerOverride(self, state: bool = False) -> None:
        """Enable player index override state"""
        self._sync.override_player_index = state

    def setPlayerIndex(self, index: int = INVALID_INDEX) -> None:
        """Manual override player index"""
        self._sync.player_index = max(index, INVALID_INDEX)

    @property
    def ams2SharedMemoryInfo(self) -> ams2_data.SharedMemory:
        """AMS2 shared memory info data"""
        return self._sync.player_shmm

    @property
    def ams2LastSectorTime(self) -> LastSectorTime:
        """AMS2 last sector time"""
        data = self._sync.player_shmm
        index = self._sync.player_index_resolved
        if not 0 <= index < AMS2Constants.STORED_PARTICIPANTS_MAX:
            index = min(
                max(data.mViewedParticipantIndex, 0),
                AMS2Constants.STORED_PARTICIPANTS_MAX - 1,
            )
        sector = data.mParticipantInfo[index].mCurrentSector
        if not 0 <= sector <= 2:  # -1 = unset, tracks may have more than 3 sectors
            sector = 0 if sector < 0 else 2
        # Cumulative completed sector time of current lap, reset values are negative
        if sector == 1:
            accumulated = max(data.mCurrentSector1Time, 0)
        elif sector == 2:
            accumulated = max(data.mCurrentSector1Time + data.mCurrentSector2Time, 0)
        else:  # new lap
            accumulated = 0.0
        return self._last_sector_time.update(
            sector,
            accumulated,
            max(data.mLastLapTime, 0),
            not data.mLapInvalidated,
        )

    @property
    def ams2ValidLap(self) -> ValidLapStatus:
        """AMS2 valid lap status"""
        data = self._sync.player_shmm
        return self._valid_lap_status.update(
            data.mCurrentTime, not data.mLapInvalidated, self._sync.resets
        )

    @property
    def ams2LastImpact(self) -> LastImpact:
        """AMS2 last impact data

        Suspension damage is used as impact reference, sorted in
        front, rear, left, right order.
        """
        susp_damage = self._sync.player_shmm.mSuspensionDamage
        return self._last_impact.update(
            self._sync.elapsed_time,
            (susp_damage[0] + susp_damage[1]) * 0.5,  # front
            (susp_damage[2] + susp_damage[3]) * 0.5,  # rear
            (susp_damage[0] + susp_damage[2]) * 0.5,  # left
            (susp_damage[1] + susp_damage[3]) * 0.5,  # right
        )

    @property
    def playerIndex(self) -> int:
        """Local player's participant index"""
        return self._sync.player_index_resolved

    @property
    def isPaused(self) -> bool:
        """Check whether data stopped updating"""
        return self._sync.paused

    @property
    def isActive(self) -> bool:
        """Check whether in active (driving or overriding) state"""
        if self._state_override:
            return self._active_state
        if self._sync.override_player_index:  # spectate only
            index = self._sync.player_index_resolved
            if not 0 <= index < AMS2Constants.STORED_PARTICIPANTS_MAX:
                return False
            return self._sync.player_shmm.mSpeeds[index] > 0
        return (
            self._sync.synced
            and self._sync.player_index_resolved >= 0
            and self._sync.player_shmm.mGameState in ACTIVE_GAME_STATES
        )

    @property
    def vehicleResets(self) -> int:
        """Number of player vehicle resets"""
        return self._sync.resets

    @property
    def elapsed(self) -> float:
        """Current session elapsed time"""
        return self._sync.elapsed_time
