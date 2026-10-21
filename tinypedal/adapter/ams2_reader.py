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
AMS2 API data reader
"""

from __future__ import annotations

from math import atan2, degrees, pi

from ..calculation import min_nonzero
from ..constant import DATA
from ..formatter import strip_invalid_char
from ..validator import bytes_decoder
from ..validator import infnan_to_zero as rmnan
from . import _reader
from .ams2_sharedmemory import AMS2Info, ams2_data

tostr = bytes_decoder()

AMS2Data = ams2_data.AMS2Constants
Terrain = ams2_data.Terrain

STEERING_RANGE_DEFAULT = 900.0  # not exposed by shared memory, assume common default


def cstr(field) -> str:
    """Decode game string field

    Struct char array field is auto-converted to bytes by ctypes, but char
    array read from nested array (ex. mCarNames[index]) stays as ctypes
    array object, which must be converted via its value attribute.
    """
    if not isinstance(field, bytes):
        field = field.value
    return tostr(field)


def ams2_sky_type(raininess: float) -> int:
    """AMS2 raininess to RF2 sky type"""
    if raininess <= 0:
        return 1  # 1 Light Clouds
    if raininess <= 0.1:
        return 5  # 5 Cloudy & Drizzle
    if raininess <= 0.25:
        return 7  # 7 Overcast & Light Rain
    if raininess <= 0.5:
        return 8  # 8 Overcast & Rain
    if raininess <= 0.75:
        return 9  # 9 Overcast & Heavy Rain
    return 10  # 10 Overcast & Storm


class DataAdapter:
    """Read & sort data into groups"""

    __slots__ = (
        "shmm",
    )

    def __init__(self, shmm: AMS2Info) -> None:
        """Initialize API setting

        Args:
            shmm: shared memory API data.
        """
        self.shmm = shmm

    def pindex(self, index: int | None) -> int:
        """Clamp participant index to stored participants range

        Negative index is possible while data is not synced yet, and ctypes
        array accepts it without bounds check (reads wrong memory), so data
        must be accessed through this clamp.
        """
        if index is None:
            index = self.shmm.playerIndex
        if index < 0:
            return 0
        if index >= AMS2Data.STORED_PARTICIPANTS_MAX:
            return AMS2Data.STORED_PARTICIPANTS_MAX - 1
        return index

    def participant(self, index: int | None) -> ams2_data.ParticipantInfo:
        """Get participant info, fall back to player participant"""
        return self.shmm.ams2SharedMemoryInfo.mParticipantInfo[self.pindex(index)]


class State(_reader.State, DataAdapter):
    """State"""

    __slots__ = ()

    def active(self) -> bool:
        """Is active (driving or overriding)"""
        return self.shmm.isActive

    def paused(self) -> bool:
        """Is paused"""
        return self.shmm.isPaused

    def resets(self) -> int:
        """Number of player vehicle resets"""
        return self.shmm.vehicleResets

    def version(self) -> str:
        """Identify API version"""
        version = self.shmm.ams2SharedMemoryInfo.mVersion
        return f"shared memory v{version}" if version else DATA.TEXT_NA


class Brake(_reader.Brake, DataAdapter):
    """Brake"""

    __slots__ = ()

    def compound_name(self, index: int | None = None) -> tuple[str, str]:
        """Brake compound name, front, rear"""
        return "", ""

    def bias_front(self, index: int | None = None) -> float:
        """Brake bias front (fraction)"""
        bias_front = rmnan(self.shmm.ams2SharedMemoryInfo.mBrakeBias)
        if bias_front < 0:  # -1 = unset
            return 0.0
        return bias_front

    def migration(self, index: int | None = None) -> float:
        """Brake migration (percent)"""
        return 0.0

    def pressure(self, index: int | None = None, scale: float = 1) -> tuple[float, ...]:
        """Brake pressure (fraction), estimated from brake input & brake bias"""
        data = self.shmm.ams2SharedMemoryInfo
        brake_input = max(rmnan(data.mBrake), 0)
        bias_front = rmnan(data.mBrakeBias)
        if bias_front < 0:  # -1 = unset
            return 0.0, 0.0, 0.0, 0.0
        return (
            brake_input * bias_front * scale,
            brake_input * bias_front * scale,
            brake_input * (1 - bias_front) * scale,
            brake_input * (1 - bias_front) * scale,
        )

    def temperature(self, index: int | None = None) -> tuple[float, ...]:
        """Brake temperature (Celsius)"""
        data = self.shmm.ams2SharedMemoryInfo.mBrakeTempCelsius
        return (
            rmnan(data[0]),
            rmnan(data[1]),
            rmnan(data[2]),
            rmnan(data[3]),
        )

    def wear(self, index: int | None = None) -> tuple[float, ...]:
        """Brake remaining thickness (meters)"""
        return DATA.WHEELS_NA


class ElectricMotor(_reader.ElectricMotor, DataAdapter):
    """Electric motor"""

    __slots__ = ()

    def state(self, index: int | None = None) -> int:
        """Motor state, 0 = n/a, 1 = off, 2 = drain, 3 = regen"""
        return 0

    def battery_charge(self, index: int | None = None) -> float:
        """Battery charge (fraction)"""
        return 0.0

    def rpm(self, index: int | None = None) -> float:
        """Motor RPM (rev per minute)"""
        return 0.0

    def torque(self, index: int | None = None) -> float:
        """Motor torque (Nm)"""
        return 0.0

    def motor_temperature(self, index: int | None = None) -> float:
        """Motor temperature (Celsius)"""
        return 0.0

    def water_temperature(self, index: int | None = None) -> float:
        """Motor water temperature (Celsius)"""
        return 0.0

    def regeneration_level(self, index: int | None = None) -> float:
        """Regeneration level (kW)"""
        return 0.0


class Engine(_reader.Engine, DataAdapter):
    """Engine"""

    __slots__ = ()

    def gear(self, index: int | None = None) -> int:
        """Gear"""
        return self.shmm.ams2SharedMemoryInfo.mGear  # per-vehicle gear not exposed

    def gear_max(self, index: int | None = None) -> int:
        """Max gear"""
        return self.shmm.ams2SharedMemoryInfo.mNumGears

    def rpm(self, index: int | None = None) -> float:
        """RPM (rev per minute)"""
        return self.shmm.ams2SharedMemoryInfo.mRpm

    def rpm_max(self, index: int | None = None) -> float:
        """Max RPM (rev per minute)"""
        return self.shmm.ams2SharedMemoryInfo.mMaxRPM

    def torque(self, index: int | None = None) -> float:
        """Torque (Nm)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mEngineTorque)

    def turbo(self, index: int | None = None) -> float:
        """Turbo pressure (Pa)"""
        return 0.0  # mTurboBoostPressure is normalized, cannot convert to Pa

    def oil_temperature(self, index: int | None = None) -> float:
        """Oil temperature (Celsius)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mOilTempCelsius)

    def water_temperature(self, index: int | None = None) -> float:
        """Water temperature (Celsius)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mWaterTempCelsius)

    def exhaust_temperature(self, index: int | None = None) -> float:
        """Exhaust temperature (Celsius)"""
        return 0.0

    def lift_and_coast_progress(self, index: int | None = None) -> float:
        """Lift and coast progress (fraction), range 0.0 to 1.0"""
        return 0.0

    def fuel(self, index: int | None = None) -> float:
        """Remaining fuel (liters)"""
        if index is None:
            data = self.shmm.ams2SharedMemoryInfo
            return rmnan(data.mFuelLevel * data.mFuelCapacity)
        return 0.0

    def fuel_fraction(self, index: int | None = None) -> float:
        """Remaining fuel (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mFuelLevel)

    def tank_capacity(self, index: int | None = None) -> float:
        """Fuel tank capacity (liters)"""
        if index is None:
            return rmnan(self.shmm.ams2SharedMemoryInfo.mFuelCapacity)
        return 0.0

    def virtual_energy(self, index: int | None = None) -> float:
        """Remaining virtual energy (fraction)"""
        return 0.0

    def max_virtual_energy(self) -> float:
        """Maximum virtual energy (joule)"""
        return 0.0

    def absolute_refill(self) -> float:
        """Absolute refill fuel (liter) or virtual energy (percent)"""
        data = self.shmm.ams2SharedMemoryInfo
        return rmnan(data.mFuelLevel * data.mFuelCapacity)


class Inputs(_reader.Inputs, DataAdapter):
    """Inputs"""

    __slots__ = ()

    def throttle(self, index: int | None = None) -> float:
        """Throttle filtered (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mThrottle)

    def throttle_raw(self, index: int | None = None) -> float:
        """Throttle raw (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mUnfilteredThrottle)

    def brake(self, index: int | None = None) -> float:
        """Brake filtered (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mBrake)

    def brake_raw(self, index: int | None = None) -> float:
        """Brake raw (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mUnfilteredBrake)

    def clutch(self, index: int | None = None) -> float:
        """Clutch filtered (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mClutch)

    def clutch_raw(self, index: int | None = None) -> float:
        """Clutch raw (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mUnfilteredClutch)

    def steering(self, index: int | None = None) -> float:
        """Steering (fraction)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mSteering)

    def steering_range(self, index: int | None = None) -> float:
        """Steering physical rotation range (degrees)"""
        return STEERING_RANGE_DEFAULT

    def force_feedback(self) -> float:
        """Steering force feedback (fraction)"""
        return 0.0


class Lap(_reader.Lap, DataAdapter):
    """Lap"""

    __slots__ = ()

    def completed(self, index: int | None = None) -> int:
        """Total completed laps"""
        return self.participant(index).mLapsCompleted

    def track_length(self) -> float:
        """Full lap or track length (meters)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mTrackLength)

    def distance(self, index: int | None = None) -> float:
        """Distance into lap (meters)"""
        return rmnan(self.participant(index).mCurrentLapDistance)

    def progress(self, index: int | None = None) -> float:
        """Lap progress (fraction), distance into lap"""
        track_length = self.track_length()
        if track_length <= 0:
            return 0.0
        return rmnan(self.participant(index).mCurrentLapDistance / track_length)

    def maximum(self) -> int:
        """Maximum lap"""
        laps = self.shmm.ams2SharedMemoryInfo.mLapsInEvent
        if 0 < laps < DATA.MAX_LAPS:
            return laps
        return DATA.MAX_LAPS

    def remaining(self, index: int | None = None) -> float:
        """Remaining lap, count from current lap progress"""
        laps_left = rmnan(self.maximum() - self.completed(index) - self.progress(index))
        if laps_left < 0:
            laps_left = 0.0
        return laps_left

    def sector_index(self, index: int | None = None) -> int:
        """Sector index, 0 = S1, 1 = S2, 2 = S3"""
        sector = self.participant(index).mCurrentSector
        if sector <= 0:
            return 0
        return min(sector, 2)

    def safety_car_distance(self) -> float:
        """Safety car's distance into lap (meters)"""
        return 0.0

    def safety_car_active(self) -> bool:
        """Is safety car active on track"""
        return False


class Session(_reader.Session, DataAdapter):
    """Session"""

    __slots__ = ()

    def combo_name(self) -> str:
        """Track & vehicle combo name, strip off invalid char"""
        class_name = cstr(self.shmm.ams2SharedMemoryInfo.mCarClassName)
        return strip_invalid_char(f"{self.track_name()} - {class_name}")

    def track_name(self) -> str:
        """Track name, strip off invalid char"""
        data = self.shmm.ams2SharedMemoryInfo
        # Ex. "Laguna_Seca" + "Laguna_Seca_2020" -> "Laguna Seca 2020",
        # "Kyalami" + "GP" -> "Kyalami GP"
        location = cstr(data.mTrackLocation).replace("_", " ").strip()
        variation = cstr(data.mTrackVariation).replace("_", " ").strip()
        if variation.lower().startswith(location.lower()):
            variation = variation[len(location):].strip(" -")
        if variation and variation.lower() != location.lower():
            location = f"{location} {variation}"
        return strip_invalid_char(location)

    def identifier(self) -> tuple[int, int, int]:
        """Identify session"""
        data = self.shmm.ams2SharedMemoryInfo
        session_stamp = int(data.mSessionState)
        session_etime = int(self.shmm.elapsed)
        session_tlaps = self.participant(None).mLapsCompleted
        return session_stamp, session_etime, session_tlaps

    def elapsed(self) -> float:
        """Session elapsed time (seconds)"""
        return self.shmm.elapsed

    def remaining(self) -> float:
        """Session time remaining (seconds), minimum limit to 0"""
        seconds = self.shmm.ams2SharedMemoryInfo.mEventTimeRemaining * 0.001
        if seconds < 0:
            seconds = 0.0
        return rmnan(seconds)

    def session_type(self) -> int:
        """Session type, 0 = TESTDAY, 1 = PRACTICE, 2 = QUALIFY, 3 = WARMUP, 4 = RACE, 5 = HOTLAP"""
        session = self.shmm.ams2SharedMemoryInfo.mSessionState
        if session == ams2_data.SessionState.SESSION_RACE:
            return 4
        if session == ams2_data.SessionState.SESSION_FORMATION_LAP:
            return 4
        if session == ams2_data.SessionState.SESSION_QUALIFY:
            return 2
        if session == ams2_data.SessionState.SESSION_PRACTICE:
            return 1
        if session == ams2_data.SessionState.SESSION_TIME_ATTACK:
            return 5
        return 0  # test day

    def finish_type(self, as_lap: bool | None = None) -> int:
        """Race finish type, 0 = time, 1 = laps only, 2 = laps & time"""
        data = self.shmm.ams2SharedMemoryInfo
        if data.mSessionDuration > 0:  # timed race
            if data.mSessionAdditionalLaps > 0:
                return 2  # laps & time
            return 0  # time
        return 1  # laps only

    def in_race(self) -> bool:
        """Is in race session"""
        session = self.shmm.ams2SharedMemoryInfo.mSessionState
        return session in (
            ams2_data.SessionState.SESSION_RACE,
            ams2_data.SessionState.SESSION_FORMATION_LAP,
        )

    def private_qualifying(self) -> bool:
        """Is private qualifying"""
        return False

    def pit_open(self) -> bool:
        """Is pit lane open"""
        state = self.shmm.ams2SharedMemoryInfo.mYellowFlagState
        return state not in (
            ams2_data.YellowFlagState.YFS_PITS_CLOSED,
            ams2_data.YellowFlagState.YFS_RACE_HALT,
        )

    def pre_race(self) -> bool:
        """Before race starts (green flag)"""
        data = self.shmm.ams2SharedMemoryInfo
        return (
            self.in_race()
            and data.mRaceState == ams2_data.RaceState.RACESTATE_NOT_STARTED
        )

    def green_flag(self) -> bool:
        """Green flag (race starts)"""
        data = self.shmm.ams2SharedMemoryInfo
        return (
            self.in_race()
            and data.mRaceState == ams2_data.RaceState.RACESTATE_RACING
        )

    def blue_flag(self, index: int | None = None) -> bool:
        """Is under blue flag"""
        data = self.shmm.ams2SharedMemoryInfo
        if index is None:
            flag_colour = data.mHighestFlagColour
        else:
            flag_colour = data.mHighestFlagColours[self.pindex(index)]
        return flag_colour == ams2_data.FlagColour.FLAG_COLOUR_BLUE

    def yellow_flag(self) -> bool:
        """Is there yellow flag in any sectors"""
        flag_colour = self.shmm.ams2SharedMemoryInfo.mHighestFlagColour
        return flag_colour in (
            ams2_data.FlagColour.FLAG_COLOUR_YELLOW,
            ams2_data.FlagColour.FLAG_COLOUR_DOUBLE_YELLOW,
        )

    def start_lights(self) -> int:
        """Start lights countdown sequence, 0=green flag, -1=no start lights"""
        return -1

    def track_temperature(self) -> float:
        """Track temperature (Celsius)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mTrackTemperature)

    def ambient_temperature(self) -> float:
        """Ambient temperature (Celsius)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mAmbientTemperature)

    def raininess(self) -> float:
        """Rain severity (fraction), range 0.0 - 1.0"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mRainDensity)

    def wetness(self) -> float:
        """Road wetness set (fraction), range 0.0 - 1.0"""
        return 0.0  # not exposed

    def weather_forecast(self) -> tuple[tuple[float, int, float, float], ...]:
        """Weather forecast nodes, 0=forecast minutes, 1=sky type index, 2=air temperature, 3=rain chance"""
        return ()  # not exposed

    def cloud_coverage(self) -> int:
        """Cloud coverage (type index), range 0 to 10

        Sky type:
            0 Clear, 1 Light Clouds, 2 Partially Cloudy, 3 Mostly Cloudy, 4 Overcast,
            5 Cloudy & Drizzle, 6 Cloudy & Light Rain, 7 Overcast & Light Rain,
            8 Overcast & Rain, 9 Overcast & Heavy Rain, 10 Overcast & Storm
        """
        return ams2_sky_type(self.shmm.ams2SharedMemoryInfo.mRainDensity)

    def grip_level(self) -> float:
        """Track base grip level, convert to fraction 0.0 to 1.0"""
        return 0.0  # not exposed

    def track_time(self, scale: int = 1) -> float:
        """Track time"""
        return 0.0  # not exposed

    def time_scale(self) -> int:
        """Time scale"""
        return 0

    def limits_points(self) -> float:
        """Track limits points per penalty"""
        return 0.0

    def cut_points(self, index: int | None = None) -> float:
        """Current track limits cut points per penalty"""
        return 0.0

    def wind_direction(self) -> float:
        """Wind direction (degrees)"""
        data = self.shmm.ams2SharedMemoryInfo
        wind_dir = rmnan(degrees(atan2(data.mWindDirectionX, data.mWindDirectionY)))
        if wind_dir < 0:
            wind_dir += 360
        return wind_dir

    def wind_speed(self) -> float:
        """Wind speed (m/s)"""
        # mWindSpeed has no documented unit, assumed miles per hour
        return rmnan(self.shmm.ams2SharedMemoryInfo.mWindSpeed * 0.44704)


class Switch(_reader.Switch, DataAdapter):
    """Switch"""

    __slots__ = ()

    def tc_level(self, index: int | None = None) -> int:
        """TC level"""
        return self.shmm.ams2SharedMemoryInfo.mTractionControlSetting

    def tc_cut_level(self, index: int | None = None) -> int:
        """TC cut level"""
        return -1

    def tc_slip_level(self, index: int | None = None) -> int:
        """TC slip level"""
        return -1

    def abs_level(self, index: int | None = None) -> int:
        """ABS level"""
        return self.shmm.ams2SharedMemoryInfo.mAntiLockSetting

    def motor_map_level(self, index: int | None = None) -> int:
        """Motor or engine map level"""
        return -1

    def brake_migration_level(self, index: int | None = None) -> int:
        """Brake migration level"""
        return -1

    def front_arb_level(self, index: int | None = None) -> int:
        """Front anti-roll bar level"""
        return -1

    def rear_arb_level(self, index: int | None = None) -> int:
        """Rear anti-roll bar level"""
        return -1

    def wipers(self, index: int | None = None) -> int:
        """Wipers state, 0 = off, 1 = auto, 2 = slow, 3 = fast"""
        return 0

    def headlights(self, index: int | None = None) -> int:
        """Headlights"""
        return int(self.shmm.ams2SharedMemoryInfo.mCarFlags & ams2_data.CarFlags.CAR_HEADLIGHT > 0)

    def ignition(self, index: int | None = None, stall_rpm: float = 100) -> int:
        """Ignition, 0=engine off, 1=ignition on, 2=engine on"""
        data = self.shmm.ams2SharedMemoryInfo
        if data.mCarFlags & ams2_data.CarFlags.CAR_ENGINE_ACTIVE:
            if data.mRpm > stall_rpm:
                return 2
            return 1
        return 0

    def speed_limiter(self, index: int | None = None) -> int:
        """Speed limiter"""
        return int(self.shmm.ams2SharedMemoryInfo.mCarFlags & ams2_data.CarFlags.CAR_SPEED_LIMITER > 0)

    def tc_active(self, index: int | None = None) -> bool:
        """TC activation state"""
        # Car flags show enabled state, intervention state is not exposed
        return self.shmm.ams2SharedMemoryInfo.mCarFlags & ams2_data.CarFlags.CAR_TCS > 0

    def abs_active(self, index: int | None = None) -> bool:
        """ABS activation state"""
        # Car flags show enabled state, intervention state is not exposed
        return self.shmm.ams2SharedMemoryInfo.mCarFlags & ams2_data.CarFlags.CAR_ABS > 0

    def drs_status(self, index: int | None = None) -> int:
        """DRS status, 0 not_available, 1 available, 2 allowed(not activated), 3 activated"""
        drs_state = self.shmm.ams2SharedMemoryInfo.mDrsState
        if drs_state & ams2_data.DrsState.DRS_ACTIVE:
            return 3
        if drs_state & ams2_data.DrsState.DRS_AVAILABLE_NOW:
            return 2
        if drs_state & ams2_data.DrsState.DRS_AVAILABLE_NEXT:
            return 1
        return 0

    def auto_clutch(self) -> bool:
        """Auto clutch"""
        return False


class Timing(_reader.Timing, DataAdapter):
    """Timing"""

    __slots__ = ()

    def elapsed(self, index: int | None = None) -> float:
        """Current elapsed time (seconds)"""
        return self.shmm.elapsed

    def is_last_valid(self, index: int | None = None) -> bool:
        """Is last lap time valid"""
        if index is None:
            return self.shmm.ams2ValidLap.last
        data = self.shmm.ams2SharedMemoryInfo
        return not data.mLapsInvalidated[self.pindex(index)]

    def current_laptime(self, index: int | None = None) -> float:
        """Current lap time (seconds)"""
        if index is None:
            return rmnan(self.shmm.ams2SharedMemoryInfo.mCurrentTime)
        return 0.0  # per-vehicle current lap time not exposed

    def last_laptime(self, index: int | None = None) -> float:
        """Last lap time (seconds), positive=valid, negative=invalid"""
        if index is None:
            data = self.shmm.ams2SharedMemoryInfo
            last = rmnan(data.mLastLapTime)
            if self.shmm.ams2ValidLap.last:
                return last
            return -last
        data = self.shmm.ams2SharedMemoryInfo
        index = self.pindex(index)
        last = rmnan(data.mLastLapTimes[index])
        if data.mLapsInvalidated[index]:
            return -last
        return last

    def best_laptime(self, index: int | None = None) -> float:
        """Best lap time (seconds)"""
        if index is None:
            return rmnan(self.shmm.ams2SharedMemoryInfo.mBestLapTime)
        return rmnan(self.shmm.ams2SharedMemoryInfo.mFastestLapTimes[self.pindex(index)])

    def reference_laptime(self, index: int | None = None, laptime: float = 0) -> float:
        """Reference lap time (seconds)"""
        if 0 < laptime < DATA.MAX_SECONDS:
            return laptime
        init_time = min_nonzero((
            self.best_laptime(index),
            abs(self.last_laptime(index)),
            DATA.MAX_SECONDS,
        ))
        if 0 < init_time < DATA.MAX_SECONDS:
            return init_time
        # Set to estimated laptime only if other laptime not available
        # as estimated laptime can be faster than other laptime
        return min_nonzero((
            self.estimated_laptime(index),
            DATA.MAX_SECONDS,
        ))

    def estimated_laptime(self, index: int | None = None) -> float:
        """Estimated lap time (seconds)"""
        track_length = self.shmm.ams2SharedMemoryInfo.mTrackLength
        if 0 < track_length < DATA.MAX_METERS:
            return track_length / 40
        return 0.0

    def estimated_time_into(self, index: int | None = None) -> float:
        """Estimated time into lap (seconds)"""
        # estimated_laptime * lap_progress = (length / 40) * (distance / length)
        return rmnan(self.participant(index).mCurrentLapDistance / 40)

    def last_sector(self, index: int | None = None) -> float:
        """Last sector time (seconds)"""
        return self.shmm.ams2LastSectorTime.last


class Tyre(_reader.Tyre, DataAdapter):
    """Tyre (front left, front right, rear left, rear right)"""

    __slots__ = ()

    def compound_name(self, index: int | None = None) -> tuple[str, ...]:
        """Tyre compound name set"""
        if index is None:
            data = self.shmm.ams2SharedMemoryInfo
            return tuple(cstr(compound) for compound in data.mTyreCompound)
        return "", "", "", ""

    def compound_class(self, index: int | None = None) -> tuple[str, ...]:
        """Tyre compound name set with class name prefix"""
        if index is None:
            data = self.shmm.ams2SharedMemoryInfo
            class_name = cstr(data.mCarClassName)
            return tuple(
                strip_invalid_char(f"{class_name} - {cstr(compound)}")
                for compound in data.mTyreCompound
            )
        return "", "", "", ""

    def surface_temperature_avg(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre surface temperature set (Celsius) average"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreTemp
        return (
            rmnan(data[0]),
            rmnan(data[1]),
            rmnan(data[2]),
            rmnan(data[3]),
        )

    def surface_temperature_ico(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre surface temperature set (Celsius) inner,center,outer"""
        data = self.shmm.ams2SharedMemoryInfo
        # Temperature edges are from car perspective:
        # outer edge of left-side tyres = left, outer edge of right-side tyres = right
        left = data.mTyreTempLeft
        center = data.mTyreTempCenter
        right = data.mTyreTempRight
        return (
            rmnan(right[0]), rmnan(center[0]), rmnan(left[0]),
            rmnan(left[1]), rmnan(center[1]), rmnan(right[1]),
            rmnan(right[2]), rmnan(center[2]), rmnan(left[2]),
            rmnan(left[3]), rmnan(center[3]), rmnan(right[3]),
        )

    def inner_temperature_avg(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre inner temperature set (Celsius) average"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreInternalAirTemp
        return tuple(
            rmnan(temp - AMS2Data.ABSOLUTE_ZERO_KELVIN) for temp in data
        )

    def inner_temperature_ico(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre inner temperature set (Celsius) inner,center,outer"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreInternalAirTemp
        return tuple(
            rmnan(temp - AMS2Data.ABSOLUTE_ZERO_KELVIN)
            for temp in data for _ in range(3)
        )

    def pressure(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre pressure (kPa)"""
        data = self.shmm.ams2SharedMemoryInfo.mAirPressure
        return (
            rmnan(data[0] * 6.89475729),  # psi to kPa
            rmnan(data[1] * 6.89475729),
            rmnan(data[2] * 6.89475729),
            rmnan(data[3] * 6.89475729),
        )

    def load(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre load (Newtons)"""
        return DATA.WHEELS_ZERO

    def wear(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre wear (fraction)"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreWear
        return (
            rmnan(data[0]),
            rmnan(data[1]),
            rmnan(data[2]),
            rmnan(data[3]),
        )

    def puncture(self, index: int | None = None, threshold: float = 1) -> tuple[bool, ...]:
        """Tyre puncture state"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreFlags
        return (
            not data[0] & ams2_data.TyreFlags.TYRE_INFLATED,
            not data[1] & ams2_data.TyreFlags.TYRE_INFLATED,
            not data[2] & ams2_data.TyreFlags.TYRE_INFLATED,
            not data[3] & ams2_data.TyreFlags.TYRE_INFLATED,
        )

    def carcass_temperature(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre carcass temperature (Celsius)"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreCarcassTemp
        return (
            rmnan(data[0] - AMS2Data.ABSOLUTE_ZERO_KELVIN),
            rmnan(data[1] - AMS2Data.ABSOLUTE_ZERO_KELVIN),
            rmnan(data[2] - AMS2Data.ABSOLUTE_ZERO_KELVIN),
            rmnan(data[3] - AMS2Data.ABSOLUTE_ZERO_KELVIN),
        )

    def vertical_deflection(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre vertical deflection (millimeters)"""
        return 1, 1, 1, 1

    def slip_angle(self, index: int | None = None) -> tuple[float, ...]:
        """Tyre slip angle (radians)"""
        return DATA.WHEELS_ZERO


class Vehicle(_reader.Vehicle, DataAdapter):
    """Vehicle"""

    __slots__ = ()

    def incidents(self, index: int | None = None) -> int:
        """Number of incidents"""
        return 0

    def is_player(self, index: int = 0) -> bool:
        """Is local player"""
        return self.shmm.playerIndex == index

    def is_driving(self) -> bool:
        """Is local player driving or in monitor"""
        return self.shmm.ams2SharedMemoryInfo.mCarFlags & ams2_data.CarFlags.CAR_ENGINE_ACTIVE > 0

    def player_index(self) -> int:
        """Get Local player index"""
        return self.shmm.playerIndex

    def slot_id(self, index: int | None = None) -> int:
        """Vehicle slot id"""
        if index is None:
            index = self.shmm.playerIndex
        return index

    def driver_name(self, index: int | None = None) -> str:
        """Driver name"""
        return cstr(self.participant(index).mName)

    def team_name(self, index: int | None = None) -> str:
        """Team name"""
        return ""

    def vehicle_model(self, index: int | None = None) -> str:
        """Vehicle model name (brand name + model ID)"""
        data = self.shmm.ams2SharedMemoryInfo
        if index is None:
            model = cstr(data.mCarName)
        else:
            model = cstr(data.mCarNames[self.pindex(index)])
        if not model:
            return "Unknown"
        return model

    def class_name(self, index: int | None = None) -> str:
        """Vehicle class name"""
        data = self.shmm.ams2SharedMemoryInfo
        if index is None:
            return cstr(data.mCarClassName)
        return cstr(data.mCarClassNames[self.pindex(index)])

    def same_class(self, index: int | None = None) -> bool:
        """Is same vehicle class"""
        return self.class_name(index) == self.class_name(self.shmm.playerIndex)

    def total_vehicles(self) -> int:
        """Total vehicles"""
        num_participants = self.shmm.ams2SharedMemoryInfo.mNumParticipants
        if num_participants < 0:
            return 0
        return min(num_participants, AMS2Data.STORED_PARTICIPANTS_MAX)

    def place(self, index: int | None = None) -> int:
        """Vehicle overall place"""
        return self.participant(index).mRacePosition

    def qualification(self, index: int | None = None) -> int:
        """Vehicle qualification place"""
        return 0

    def pit_mode(self, index: int | None = None) -> int:
        """Pit mode"""
        if index is None:
            return self.shmm.ams2SharedMemoryInfo.mPitMode
        return self.shmm.ams2SharedMemoryInfo.mPitModes[self.pindex(index)]

    def in_pits(self, index: int | None = None) -> bool:
        """Is in pits"""
        return self.pit_mode(index) in (
            ams2_data.PitMode.PIT_MODE_DRIVING_INTO_PITS,
            ams2_data.PitMode.PIT_MODE_IN_PIT,
            ams2_data.PitMode.PIT_MODE_DRIVING_OUT_OF_PITS,
        )

    def in_garage(self, index: int | None = None) -> bool:
        """Is in garage"""
        return self.pit_mode(index) in (
            ams2_data.PitMode.PIT_MODE_IN_GARAGE,
            ams2_data.PitMode.PIT_MODE_DRIVING_OUT_OF_GARAGE,
        )

    def in_paddock(self, index: int | None = None) -> int:
        """Is in paddock (either pit lane or garage), 0 = on track, 1 = pit lane, 2 = garage"""
        if self.in_garage(index):
            return 2
        return int(self.in_pits(index))

    def number_pitstops(self, index: int | None = None, penalty: int = 0) -> int:
        """Number of pit stops"""
        return -penalty if penalty else 0  # not exposed

    def number_penalties(self, index: int | None = None) -> int:
        """Number of penalties"""
        return 0

    def pit_request(self, index: int | None = None) -> bool:
        """Is requested pit, 0 = none, 1 = request, 2 = entering, 3 = stopped, 4 = exiting"""
        if index is None:
            schedule = self.shmm.ams2SharedMemoryInfo.mPitSchedule
        else:
            schedule = self.shmm.ams2SharedMemoryInfo.mPitSchedules[self.pindex(index)]
        return schedule not in (
            ams2_data.PitSchedule.PIT_SCHEDULE_NONE,
            ams2_data.PitSchedule.PIT_SCHEDULE_PITSPOT_OCCUPIED,
        )

    def pit_stop_time(self) -> float:
        """Estimated pit stop time (seconds)"""
        return 0.0

    def repair_time(self) -> float:
        """Scheduled repair time (seconds)"""
        return 0.0

    def finish_state(self, index: int | None = None) -> int:
        """Finish state, 0 = none, 1 = finished, 2 = DNF, 3 = DQ"""
        if index is None:
            race_state = self.shmm.ams2SharedMemoryInfo.mRaceState
        else:
            race_state = self.shmm.ams2SharedMemoryInfo.mRaceStates[self.pindex(index)]
        if race_state == ams2_data.RaceState.RACESTATE_FINISHED:
            return 1
        if race_state in (
            ams2_data.RaceState.RACESTATE_DNF,
            ams2_data.RaceState.RACESTATE_RETIRED,
        ):
            return 2
        if race_state == ams2_data.RaceState.RACESTATE_DISQUALIFIED:
            return 3
        return 0

    def orientation_yaw(self, index: int | None = None) -> float:
        """Orientation yaw (radians)"""
        if index is None:
            return rmnan(-self.shmm.ams2SharedMemoryInfo.mOrientation[0])
        return rmnan(-self.shmm.ams2SharedMemoryInfo.mOrientations[self.pindex(index)][0])

    def position_xyz(self, index: int | None = None) -> tuple[float, float, float]:
        """Raw x,y,z position (meters)"""
        pos = self.participant(index).mWorldPosition
        return rmnan(pos[0]), rmnan(pos[1]), rmnan(pos[2])

    def position_longitudinal(self, index: int | None = None) -> float:
        """Longitudinal axis position (meters) related to world plane"""
        return rmnan(self.participant(index).mWorldPosition[0])  # X in AMS2 coord system

    def position_lateral(self, index: int | None = None) -> float:
        """Lateral axis position (meters) related to world plane"""
        return rmnan(self.participant(index).mWorldPosition[2])  # Z in AMS2 coord system

    def position_vertical(self, index: int | None = None) -> float:
        """Vertical axis position (meters) related to world plane"""
        return rmnan(self.participant(index).mWorldPosition[1])  # Y in AMS2 coord system

    def acceleration_lateral(self, index: int | None = None) -> float:
        """Lateral acceleration (m/s^2)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mLocalAcceleration[0])  # X in AMS2 coord system

    def acceleration_longitudinal(self, index: int | None = None) -> float:
        """Longitudinal acceleration (m/s^2)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mLocalAcceleration[2])  # Z in AMS2 coord system

    def acceleration_vertical(self, index: int | None = None) -> float:
        """Vertical acceleration (m/s^2)"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mLocalAcceleration[1])  # Y in AMS2 coord system

    def velocity_lateral(self, index: int | None = None) -> float:
        """Lateral velocity (m/s) x"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mLocalVelocity[0])  # X in AMS2 coord system

    def velocity_longitudinal(self, index: int | None = None) -> float:
        """Longitudinal velocity (m/s) y"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mLocalVelocity[2])  # Z in AMS2 coord system

    def velocity_vertical(self, index: int | None = None) -> float:
        """Vertical velocity (m/s) z"""
        return rmnan(self.shmm.ams2SharedMemoryInfo.mLocalVelocity[1])  # Y in AMS2 coord system

    def speed(self, index: int | None = None) -> float:
        """Speed (m/s)"""
        if index is None:
            return rmnan(self.shmm.ams2SharedMemoryInfo.mSpeed)
        return rmnan(self.shmm.ams2SharedMemoryInfo.mSpeeds[self.pindex(index)])

    def downforce_front(self, index: int | None = None) -> float:
        """Downforce front (Newtons)"""
        return 0.0

    def downforce_rear(self, index: int | None = None) -> float:
        """Downforce rear (Newtons)"""
        return 0.0

    def damage_severity(self, index: int | None = None) -> tuple[float, ...]:
        """Damage severity, sort row by row from left to right, top to bottom"""
        # Per-panel damage is not exposed
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    def aero_damage(self, index: int | None = None) -> float:
        """Aerodynamic damage (fraction), -1.0 unavailable, 0.0 no damage, 1.0 totaled"""
        if index is None:
            return rmnan(self.shmm.ams2SharedMemoryInfo.mAeroDamage)
        return -1.0

    def integrity(self, index: int | None = None) -> float:
        """Vehicle integrity"""
        if index is None:
            data = self.shmm.ams2SharedMemoryInfo
            return rmnan(1 - (data.mAeroDamage + data.mEngineDamage) * 0.5)
        return 1.0

    def is_detached(self, index: int | None = None) -> bool:
        """Whether any vehicle parts are detached"""
        return False

    def impact_time(self, index: int | None = None) -> float:
        """Last impact time stamp (seconds)"""
        return self.shmm.ams2LastImpact.timestamp

    def impact_position(self, index: int | None = None) -> tuple[float, float]:
        """Last impact position x,y coordinates"""
        return self.shmm.ams2LastImpact.position

    def setup(self) -> tuple[str, ...]:
        """Car setup data"""
        return ()


class Wheel(_reader.Wheel, DataAdapter):
    """Wheel & suspension (front left, front right, rear left, rear right)"""

    __slots__ = ()

    def track_front(self, index: int | None = None) -> float:
        """Wheel track front (millimeters)"""
        return 0.0

    def track_rear(self, index: int | None = None) -> float:
        """Wheel track rear (millimeters)"""
        return 0.0

    def wheelbase(self, index: int | None = None) -> float:
        """Wheelbase (millimeters)"""
        return 0.0

    def camber(self, index: int | None = None) -> tuple[float, ...]:
        """Wheel camber (radians)"""
        return DATA.WHEELS_ZERO

    def toe(self, index: int | None = None) -> tuple[float, ...]:
        """Wheel toe (radians)"""
        return DATA.WHEELS_ZERO

    def rotation(self, index: int | None = None) -> tuple[float, ...]:
        """Wheel rotation (radians per second), or angular velocity"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreRPS
        return (
            rmnan(data[0] * 2 * pi),  # rps to radians per second
            rmnan(data[1] * 2 * pi),
            rmnan(data[2] * 2 * pi),
            rmnan(data[3] * 2 * pi),
        )

    def ride_height(self, index: int | None = None) -> tuple[float, ...]:
        """Ride height (convert meters to millimeters)"""
        data = self.shmm.ams2SharedMemoryInfo.mRideHeight
        return (
            rmnan(data[0]) * 10,  # centimeters to millimeters
            rmnan(data[1]) * 10,
            rmnan(data[2]) * 10,
            rmnan(data[3]) * 10,
        )

    def third_spring_deflection(self, index: int | None = None) -> tuple[float, ...]:
        """Third spring deflection front & rear (convert meters to millimeters)"""
        return DATA.WHEELS_ZERO

    def suspension_deflection(self, index: int | None = None) -> tuple[float, ...]:
        """Suspension deflection (convert meters to millimeters)"""
        data = self.shmm.ams2SharedMemoryInfo.mSuspensionTravel
        return (
            rmnan(data[0]) * 1000,
            rmnan(data[1]) * 1000,
            rmnan(data[2]) * 1000,
            rmnan(data[3]) * 1000,
        )

    def suspension_force(self, index: int | None = None) -> tuple[float, ...]:
        """Suspension force (Newtons)"""
        return DATA.WHEELS_ZERO

    def suspension_damage(self, index: int | None = None) -> tuple[float, ...]:
        """Suspension damage (fraction), 0.0 no damage, 1.0 totaled"""
        data = self.shmm.ams2SharedMemoryInfo.mSuspensionDamage
        return (
            rmnan(data[0]),
            rmnan(data[1]),
            rmnan(data[2]),
            rmnan(data[3]),
        )

    def position_vertical(self, index: int | None = None) -> tuple[float, ...]:
        """Vertical wheel position (convert meters to millimeters) related to vehicle"""
        data = self.shmm.ams2SharedMemoryInfo.mWheelLocalPositionY
        return (
            rmnan(data[0]) * 1000,
            rmnan(data[1]) * 1000,
            rmnan(data[2]) * 1000,
            rmnan(data[3]) * 1000,
        )

    def is_detached(self, index: int | None = None) -> tuple[bool, ...]:
        """Whether wheel is detached"""
        data = self.shmm.ams2SharedMemoryInfo.mTyreFlags
        return (
            not data[0] & ams2_data.TyreFlags.TYRE_ATTACHED,
            not data[1] & ams2_data.TyreFlags.TYRE_ATTACHED,
            not data[2] & ams2_data.TyreFlags.TYRE_ATTACHED,
            not data[3] & ams2_data.TyreFlags.TYRE_ATTACHED,
        )

    def offroad(self, index: int | None = None) -> int:
        """Number of wheels currently off the road"""
        if index is not None:  # per-vehicle terrain not exposed
            return 0
        return sum(
            terrain not in Terrain.ROAD_LIKE
            for terrain in self.shmm.ams2SharedMemoryInfo.mTerrain
        )
