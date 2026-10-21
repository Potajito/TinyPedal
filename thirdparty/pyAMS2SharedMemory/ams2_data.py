"""
Python mapping of Automobilista 2's Shared Memory Interface

This library is based on the official "AMS2 SharedMemoryExampleApp":
found in game's "Support/SharedMemory" folder, which is compatible
with the "Project Cars 2" in-game shared memory option.

Type hints & annotation:
- Annotate "ctypes type" as "Python type" according to table from:
  https://docs.python.org/3/library/ctypes.html#fundamental-data-types
- Annotate array object as list[type].

Notes:
- C struct uses natural field alignment (no packing), which matches
  ctypes.Structure default behavior.
- Strings are 1-byte char arrays (bytes), decode via configured encoding.
"""

from __future__ import annotations

import ctypes
import os
import sys

from ._common import _t, typedstruct


# Constants
class AMS2Constants:
    """AMS2 constants"""

    # Windows: named file mapping in local namespace
    # Linux: file in /dev/shm/, exposed by the Wine/Proton bridge (no "Local\\" prefix)
    _MM_PREFIX: str = "Local\\" if sys.platform == "win32" else ""
    MM_SHARED_MEMORY_NAME = f"{_MM_PREFIX}$pcars2$"

    SHARED_MEMORY_VERSION: int = 14
    STRING_LENGTH_MAX: int = 64
    TYRE_COMPOUND_NAME_LENGTH_MAX: int = 40
    STORED_PARTICIPANTS_MAX: int = 64
    TYRE_MAX: int = 4
    VEC_MAX: int = 3

    INVALID_PARTICIPANT_INDEX: int = -1
    INVALID_SECTOR_INDEX: int = -1

    ABSOLUTE_ZERO_KELVIN: float = 273.15  # offset to convert Kelvin to Celsius

    LOG_PATH: str = f"{os.getenv('LOCALAPPDATA', '.')}\\Automobilista 2\\Logs"


# Tyre & vector index
TYRE_FRONT_LEFT = 0
TYRE_FRONT_RIGHT = 1
TYRE_REAR_LEFT = 2
TYRE_REAR_RIGHT = 3
VEC_X = 0
VEC_Y = 1
VEC_Z = 2


class GameState:
    """(Type#1) Game state"""

    GAME_EXITED = 0
    GAME_FRONT_END = 1
    GAME_INGAME_PLAYING = 2
    GAME_INGAME_PAUSED = 3
    GAME_INGAME_INMENU_TIME_TICKING = 4
    GAME_INGAME_RESTARTING = 5
    GAME_INGAME_REPLAY = 6
    GAME_FRONT_END_REPLAY = 7


class SessionState:
    """(Type#2) Session state"""

    SESSION_INVALID = 0
    SESSION_PRACTICE = 1
    SESSION_TEST = 2
    SESSION_QUALIFY = 3
    SESSION_FORMATION_LAP = 4
    SESSION_RACE = 5
    SESSION_TIME_ATTACK = 6


class RaceState:
    """(Type#3) Race state"""

    RACESTATE_INVALID = 0
    RACESTATE_NOT_STARTED = 1
    RACESTATE_RACING = 2
    RACESTATE_FINISHED = 3
    RACESTATE_DISQUALIFIED = 4
    RACESTATE_RETIRED = 5
    RACESTATE_DNF = 6


class FlagColour:
    """(Type#5) Flag colours"""

    FLAG_COLOUR_NONE = 0
    FLAG_COLOUR_GREEN = 1
    FLAG_COLOUR_BLUE = 2
    FLAG_COLOUR_WHITE_SLOW_CAR = 3
    FLAG_COLOUR_WHITE_FINAL_LAP = 4
    FLAG_COLOUR_RED = 5
    FLAG_COLOUR_YELLOW = 6
    FLAG_COLOUR_DOUBLE_YELLOW = 7
    FLAG_COLOUR_BLACK_AND_WHITE = 8
    FLAG_COLOUR_BLACK_ORANGE_CIRCLE = 9
    FLAG_COLOUR_BLACK = 10
    FLAG_COLOUR_CHEQUERED = 11


class PitMode:
    """(Type#7) Pit mode"""

    PIT_MODE_NONE = 0
    PIT_MODE_DRIVING_INTO_PITS = 1
    PIT_MODE_IN_PIT = 2
    PIT_MODE_DRIVING_OUT_OF_PITS = 3
    PIT_MODE_IN_GARAGE = 4
    PIT_MODE_DRIVING_OUT_OF_GARAGE = 5


class PitSchedule:
    """(Type#8) Pit stop schedule"""

    PIT_SCHEDULE_NONE = 0
    PIT_SCHEDULE_PLAYER_REQUESTED = 1
    PIT_SCHEDULE_ENGINEER_REQUESTED = 2
    PIT_SCHEDULE_DAMAGE_REQUESTED = 3
    PIT_SCHEDULE_MANDATORY = 4
    PIT_SCHEDULE_DRIVE_THROUGH = 5
    PIT_SCHEDULE_STOP_GO = 6
    PIT_SCHEDULE_PITSPOT_OCCUPIED = 7


class CarFlags:
    """(Type#9) Car flags (bitmask)"""

    CAR_HEADLIGHT = (1 << 0)
    CAR_ENGINE_ACTIVE = (1 << 1)
    CAR_ENGINE_WARNING = (1 << 2)
    CAR_SPEED_LIMITER = (1 << 3)
    CAR_ABS = (1 << 4)
    CAR_HANDBRAKE = (1 << 5)
    CAR_TCS = (1 << 6)
    CAR_SCS = (1 << 7)


class TyreFlags:
    """(Type#10) Tyre flags (bitmask)"""

    TYRE_ATTACHED = (1 << 0)
    TYRE_INFLATED = (1 << 1)
    TYRE_IS_ON_GROUND = (1 << 2)


class CrashDamageState:
    """(Type#12) Crash damage state"""

    CRASH_DAMAGE_NONE = 0
    CRASH_DAMAGE_OFFTRACK = 1
    CRASH_DAMAGE_LARGE_PROP = 2
    CRASH_DAMAGE_SPINNING = 3
    CRASH_DAMAGE_ROLLING = 4


class DrsState:
    """(Type#14) DRS state (bitmask)"""

    DRS_INSTALLED = (1 << 0)
    DRS_ZONE_RULES = (1 << 1)
    DRS_AVAILABLE_NEXT = (1 << 2)
    DRS_AVAILABLE_NOW = (1 << 3)
    DRS_ACTIVE = (1 << 4)


class YellowFlagState:
    """(Type#16) Yellow flag state (FCY)"""

    YFS_INVALID = -1
    YFS_NONE = 0
    YFS_PENDING = 1
    YFS_PITS_CLOSED = 2
    YFS_PIT_LEAD_LAP = 3
    YFS_PITS_OPEN = 4
    YFS_PITS_OPEN2 = 5
    YFS_LAST_LAP = 6
    YFS_RESUME = 7
    YFS_RACE_HALT = 8


class Terrain:
    """(Type#11) Terrain materials"""

    TERRAIN_ROAD = 0
    TERRAIN_LOW_GRIP_ROAD = 1
    TERRAIN_BUMPY_ROAD1 = 2
    TERRAIN_BUMPY_ROAD2 = 3
    TERRAIN_BUMPY_ROAD3 = 4
    TERRAIN_MARBLES = 5
    TERRAIN_GRASSY_BERMS = 6
    TERRAIN_GRASS = 7
    TERRAIN_GRAVEL = 8
    TERRAIN_BUMPY_GRAVEL = 9
    TERRAIN_RUMBLE_STRIPS = 10
    TERRAIN_DRAINS = 11
    TERRAIN_TYREWALLS = 12
    TERRAIN_CEMENTWALLS = 13
    TERRAIN_GUARDRAILS = 14
    TERRAIN_SAND = 15
    TERRAIN_BUMPY_SAND = 16
    TERRAIN_DIRT = 17
    TERRAIN_BUMPY_DIRT = 18
    TERRAIN_DIRT_ROAD = 19
    TERRAIN_BUMPY_DIRT_ROAD = 20
    TERRAIN_PAVEMENT = 21
    TERRAIN_DIRT_BANK = 22
    TERRAIN_WOOD = 23
    TERRAIN_DRY_VERGE = 24
    TERRAIN_EXIT_RUMBLE_STRIPS = 25
    TERRAIN_GRASSCRETE = 26
    TERRAIN_LONG_GRASS = 27
    TERRAIN_SLOPE_GRASS = 28
    TERRAIN_COBBLES = 29
    TERRAIN_SAND_ROAD = 30
    TERRAIN_BAKED_CLAY = 31
    TERRAIN_ASTROTURF = 32
    TERRAIN_SNOWHALF = 33
    TERRAIN_SNOWFULL = 34
    TERRAIN_DAMAGED_ROAD1 = 35
    TERRAIN_TRAIN_TRACK_ROAD = 36
    TERRAIN_BUMPYCOBBLES = 37
    TERRAIN_ARIES_ONLY = 38
    TERRAIN_ORION_ONLY = 39
    TERRAIN_B1RUMBLES = 40
    TERRAIN_B2RUMBLES = 41
    TERRAIN_ROUGH_SAND_MEDIUM = 42
    TERRAIN_ROUGH_SAND_HEAVY = 43
    TERRAIN_SNOWWALLS = 44
    TERRAIN_ICE_ROAD = 45
    TERRAIN_RUNOFF_ROAD = 46
    TERRAIN_ILLEGAL_STRIP = 47
    TERRAIN_PAINT_CONCRETE = 48
    TERRAIN_PAINT_CONCRETE_ILLEGAL = 49
    TERRAIN_RALLY_TARMAC = 50

    # Terrain types considered on-road surface
    ROAD_LIKE = frozenset((
        TERRAIN_ROAD,
        TERRAIN_LOW_GRIP_ROAD,
        TERRAIN_RUMBLE_STRIPS,
        TERRAIN_EXIT_RUMBLE_STRIPS,
        TERRAIN_B1RUMBLES,
        TERRAIN_B2RUMBLES,
        TERRAIN_ILLEGAL_STRIP,
    ))


# Structs
@typedstruct
class ParticipantInfo(ctypes.Structure):
    """(Type#13) Participant info struct

    Attributes:
        mIsActive: Is participant active.
        mName: Participant name.
        mWorldPosition: World position [X, Y(up), Z] (meters).
        mCurrentLapDistance: Distance into lap (meters).
        mRacePosition: Race position, 1 = 1st.
        mLapsCompleted: Total completed laps.
        mCurrentLap: Current lap number.
        mCurrentSector: Current sector index, 0-based, -1 = unset.
    """

    __slots__ = ()

    mIsActive: bool = _t(ctypes.c_bool)
    mName: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)
    mWorldPosition: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mCurrentLapDistance: float = _t(ctypes.c_float)
    mRacePosition: int = _t(ctypes.c_uint)
    mLapsCompleted: int = _t(ctypes.c_uint)
    mCurrentLap: int = _t(ctypes.c_uint)
    mCurrentSector: int = _t(ctypes.c_int)


@typedstruct
class SharedMemory(ctypes.Structure):
    """Mapping of AMS2 'SharedMemory' (shared memory version 14)

    Attributes:
        mVersion: Shared memory version number.
        mBuildVersionNumber: Game build version number.
        mGameState: Game state.
        mSessionState: Session state.
        mRaceState: Race state.
        mViewedParticipantIndex: Viewed (local) participant index, -1 = unset.
        mNumParticipants: Number of active participants, -1 = unset.
        mParticipantInfo: Participant info array.
        mUnfilteredThrottle: Raw throttle input (fraction).
        mUnfilteredBrake: Raw brake input (fraction).
        mUnfilteredSteering: Raw steering input (fraction).
        mUnfilteredClutch: Raw clutch input (fraction).
        mCarName: Viewed car name.
        mCarClassName: Viewed car class name.
        mLapsInEvent: Total event laps, 0 = unset (timed event).
        mTrackLocation: Track location name (untranslated shortened English name).
        mTrackVariation: Track variation name.
        mTrackLength: Track length (meters).
        mNumSectors: Number of sectors.
        mLapInvalidated: Is current lap invalidated.
        mBestLapTime: Best lap time (seconds).
        mLastLapTime: Last lap time (seconds).
        mCurrentTime: Current lap time (seconds).
        mSplitTimeAhead: Time ahead of participant ahead (seconds).
        mSplitTimeBehind: Time behind participant behind (seconds).
        mSplitTime: Sector split time (seconds).
        mEventTimeRemaining: Event time remaining (milliseconds), -1.0 = unset.
        mPersonalFastestLapTime: Personal fastest lap time (seconds).
        mWorldFastestLapTime: World fastest lap time (seconds).
        mCurrentSector1Time: Current lap sector 1 time (seconds), -1.0 = unset.
        mCurrentSector2Time: Current lap sector 2 time (seconds), -1.0 = unset.
        mCurrentSector3Time: Current lap sector 3 time (seconds), -1.0 = unset.
        mFastestSector1Time: Session fastest sector 1 time (seconds), -1.0 = unset.
        mFastestSector2Time: Session fastest sector 2 time (seconds), -1.0 = unset.
        mFastestSector3Time: Session fastest sector 3 time (seconds), -1.0 = unset.
        mPersonalFastestSector1Time: Personal fastest sector 1 time (seconds), -1.0 = unset.
        mPersonalFastestSector2Time: Personal fastest sector 2 time (seconds), -1.0 = unset.
        mPersonalFastestSector3Time: Personal fastest sector 3 time (seconds), -1.0 = unset.
        mWorldFastestSector1Time: World fastest sector 1 time (seconds), -1.0 = unset.
        mWorldFastestSector2Time: World fastest sector 2 time (seconds), -1.0 = unset.
        mWorldFastestSector3Time: World fastest sector 3 time (seconds), -1.0 = unset.
        mHighestFlagColour: Highest flag colour.
        mHighestFlagReason: Highest flag reason.
        mPitMode: Viewed participant pit mode.
        mPitSchedule: Viewed participant pit stop schedule.
        mCarFlags: Car flags bitmask.
        mOilTempCelsius: Oil temperature (Celsius).
        mOilPressureKPa: Oil pressure (kPa).
        mWaterTempCelsius: Water temperature (Celsius).
        mWaterPressureKPa: Water pressure (kPa).
        mFuelPressureKPa: Fuel pressure (kPa).
        mFuelLevel: Fuel level (fraction 0.0-1.0).
        mFuelCapacity: Fuel tank capacity (liters).
        mSpeed: Speed (meters per second).
        mRpm: Engine RPM.
        mMaxRPM: Maximum engine RPM.
        mBrake: Brake input (fraction).
        mThrottle: Throttle input (fraction).
        mClutch: Clutch input (fraction).
        mSteering: Steering input (fraction).
        mGear: Gear, -1 = reverse, 0 = neutral, 1+ = forward gears.
        mNumGears: Number of gears.
        mOdometerKM: Odometer (kilometers), -1.0 = unset.
        mAntiLockActive: Is ABS active.
        mLastOpponentCollisionIndex: Last collided opponent participant index, -1 = none.
        mLastOpponentCollisionMagnitude: Last collision magnitude.
        mBoostActive: Is boost active.
        mBoostAmount: Boost amount (fraction 0.0-100.0).
        mOrientation: Orientation Euler angles (radians) [yaw, pitch, roll].
        mLocalVelocity: Local velocity (meters per second).
        mWorldVelocity: World velocity (meters per second).
        mAngularVelocity: Angular velocity (radians per second).
        mLocalAcceleration: Local acceleration (meters per second squared).
        mWorldAcceleration: World acceleration (meters per second squared).
        mExtentsCentre: Car extents centre (local space).
        mTyreFlags: Tyre flags bitmask set [FL, FR, RL, RR].
        mTerrain: Terrain material set [FL, FR, RL, RR].
        mTyreY: Tyre local Y position set (meters).
        mTyreRPS: Tyre rotation speed set (revolutions per second).
        mTyreSlipSpeed: (OBSOLETE) Tyre slip speed set.
        mTyreTemp: Tyre surface temperature set (Celsius).
        mTyreGrip: (OBSOLETE) Tyre grip set.
        mTyreHeightAboveGround: Tyre height above ground set (meters).
        mTyreLateralStiffness: (OBSOLETE) Tyre lateral stiffness set.
        mTyreWear: Tyre wear set (fraction).
        mBrakeDamage: Brake damage set (fraction 0.0-1.0).
        mSuspensionDamage: Suspension damage set (fraction 0.0-1.0).
        mBrakeTempCelsius: Brake temperature set (Celsius).
        mTyreTreadTemp: Tyre tread temperature set (Kelvin).
        mTyreLayerTemp: Tyre layer temperature set (Kelvin).
        mTyreCarcassTemp: Tyre carcass temperature set (Kelvin).
        mTyreRimTemp: Tyre rim temperature set (Kelvin).
        mTyreInternalAirTemp: Tyre internal air temperature set (Kelvin).
        mCrashState: Crash damage state.
        mAeroDamage: Aerodynamic damage (fraction 0.0-1.0).
        mEngineDamage: Engine damage (fraction 0.0-1.0).
        mAmbientTemperature: Ambient temperature (Celsius), unset = 25.0.
        mTrackTemperature: Track temperature (Celsius), unset = 30.0.
        mRainDensity: Rain density (fraction 0.0-1.0).
        mWindSpeed: Wind speed, range 0.0-100.0, unset = 2.0.
        mWindDirectionX: Wind direction normalized vector X.
        mWindDirectionY: Wind direction normalized vector Y.
        mCloudBrightness: Cloud brightness.
        mSequenceNumber: Sequence number, odd = data being written, even = data stable.
        mWheelLocalPositionY: Wheel local Y position set (meters).
        mSuspensionTravel: Suspension travel set (meters).
        mSuspensionVelocity: Suspension velocity set.
        mAirPressure: Tyre air pressure set (PSI).
        mEngineSpeed: Engine speed (radians per second).
        mEngineTorque: Engine torque (Newton meters).
        mWings: Wing settings (fraction 0.0-1.0) [front, rear].
        mHandBrake: Handbrake input (fraction).
        mCurrentSector1Times: Current sector 1 time set (seconds), -1.0 = unset.
        mCurrentSector2Times: Current sector 2 time set (seconds), -1.0 = unset.
        mCurrentSector3Times: Current sector 3 time set (seconds), -1.0 = unset.
        mFastestSector1Times: Fastest sector 1 time set (seconds), -1.0 = unset.
        mFastestSector2Times: Fastest sector 2 time set (seconds), -1.0 = unset.
        mFastestSector3Times: Fastest sector 3 time set (seconds), -1.0 = unset.
        mFastestLapTimes: Fastest lap time set (seconds), -1.0 = unset.
        mLastLapTimes: Last lap time set (seconds), -1.0 = unset.
        mLapsInvalidated: Laps invalidated set.
        mRaceStates: Race state set.
        mPitModes: Pit mode set.
        mOrientations: Orientation Euler angles set (radians) [yaw, pitch, roll].
        mSpeeds: Speed set (meters per second).
        mCarNames: Car name set.
        mCarClassNames: Car class name set.
        mEnforcedPitStopLap: Enforced pit stop lap, -1 = unset.
        mTranslatedTrackLocation: Translated track location name.
        mTranslatedTrackVariation: Translated track variation name.
        mBrakeBias: Brake bias (front fraction 0.0-1.0), -1.0 = unset.
        mTurboBoostPressure: Turbo boost pressure (fraction 0.0-1.0), -1.0 = unset.
        mTyreCompound: Tyre compound name set.
        mPitSchedules: Pit stop schedule set.
        mHighestFlagColours: Highest flag colour set.
        mHighestFlagReasons: Highest flag reason set.
        mNationalities: Nationality table set.
        mSnowDensity: Snow density (fraction 0.0-1.0).
        mSessionDuration: Scheduled session duration (minutes), 0.0 = laps race.
        mSessionAdditionalLaps: Additional laps for timed race.
        mTyreTempLeft: Tyre left edge temperature set (Celsius).
        mTyreTempCenter: Tyre center temperature set (Celsius).
        mTyreTempRight: Tyre right edge temperature set (Celsius).
        mDrsState: DRS state bitmask.
        mRideHeight: Ride height set (centimeters).
        mJoyPad0: Joypad button mask.
        mDPad: DPad button mask.
        mAntiLockSetting: ABS garage setting, -1 = unset.
        mTractionControlSetting: TC garage setting, -1 = unset.
        mErsDeploymentMode: ERS deployment mode.
        mErsAutoModeEnabled: Is ERS deployment mode selected by auto system.
        mClutchTemp: Clutch temperature (Kelvin), unset = -273.16.
        mClutchWear: Clutch wear (fraction 0.0-1.0).
        mClutchOverheated: Is clutch performance degraded by overheating.
        mClutchSlipping: Is clutch slipping.
        mYellowFlagState: Yellow flag state (FCY).
        mSessionIsPrivate: Is private session.
        mLaunchStage: Launch control stage.
    """

    __slots__ = ()

    # Version Number
    mVersion: int = _t(ctypes.c_uint)
    mBuildVersionNumber: int = _t(ctypes.c_uint)

    # Game States
    mGameState: int = _t(ctypes.c_uint)
    mSessionState: int = _t(ctypes.c_uint)
    mRaceState: int = _t(ctypes.c_uint)

    # Participant Info
    mViewedParticipantIndex: int = _t(ctypes.c_int)
    mNumParticipants: int = _t(ctypes.c_int)
    mParticipantInfo: list[ParticipantInfo] = _t(ParticipantInfo * AMS2Constants.STORED_PARTICIPANTS_MAX)

    # Unfiltered Input
    mUnfilteredThrottle: float = _t(ctypes.c_float)
    mUnfilteredBrake: float = _t(ctypes.c_float)
    mUnfilteredSteering: float = _t(ctypes.c_float)
    mUnfilteredClutch: float = _t(ctypes.c_float)

    # Vehicle information
    mCarName: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)
    mCarClassName: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)

    # Event information
    mLapsInEvent: int = _t(ctypes.c_uint)
    mTrackLocation: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)
    mTrackVariation: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)
    mTrackLength: float = _t(ctypes.c_float)

    # Timings
    mNumSectors: int = _t(ctypes.c_int)
    mLapInvalidated: bool = _t(ctypes.c_bool)
    mBestLapTime: float = _t(ctypes.c_float)
    mLastLapTime: float = _t(ctypes.c_float)
    mCurrentTime: float = _t(ctypes.c_float)
    mSplitTimeAhead: float = _t(ctypes.c_float)
    mSplitTimeBehind: float = _t(ctypes.c_float)
    mSplitTime: float = _t(ctypes.c_float)
    mEventTimeRemaining: float = _t(ctypes.c_float)
    mPersonalFastestLapTime: float = _t(ctypes.c_float)
    mWorldFastestLapTime: float = _t(ctypes.c_float)
    mCurrentSector1Time: float = _t(ctypes.c_float)
    mCurrentSector2Time: float = _t(ctypes.c_float)
    mCurrentSector3Time: float = _t(ctypes.c_float)
    mFastestSector1Time: float = _t(ctypes.c_float)
    mFastestSector2Time: float = _t(ctypes.c_float)
    mFastestSector3Time: float = _t(ctypes.c_float)
    mPersonalFastestSector1Time: float = _t(ctypes.c_float)
    mPersonalFastestSector2Time: float = _t(ctypes.c_float)
    mPersonalFastestSector3Time: float = _t(ctypes.c_float)
    mWorldFastestSector1Time: float = _t(ctypes.c_float)
    mWorldFastestSector2Time: float = _t(ctypes.c_float)
    mWorldFastestSector3Time: float = _t(ctypes.c_float)

    # Flags
    mHighestFlagColour: int = _t(ctypes.c_uint)
    mHighestFlagReason: int = _t(ctypes.c_uint)

    # Pit Info
    mPitMode: int = _t(ctypes.c_uint)
    mPitSchedule: int = _t(ctypes.c_uint)

    # Car State
    mCarFlags: int = _t(ctypes.c_uint)
    mOilTempCelsius: float = _t(ctypes.c_float)
    mOilPressureKPa: float = _t(ctypes.c_float)
    mWaterTempCelsius: float = _t(ctypes.c_float)
    mWaterPressureKPa: float = _t(ctypes.c_float)
    mFuelPressureKPa: float = _t(ctypes.c_float)
    mFuelLevel: float = _t(ctypes.c_float)
    mFuelCapacity: float = _t(ctypes.c_float)
    mSpeed: float = _t(ctypes.c_float)
    mRpm: float = _t(ctypes.c_float)
    mMaxRPM: float = _t(ctypes.c_float)
    mBrake: float = _t(ctypes.c_float)
    mThrottle: float = _t(ctypes.c_float)
    mClutch: float = _t(ctypes.c_float)
    mSteering: float = _t(ctypes.c_float)
    mGear: int = _t(ctypes.c_int)
    mNumGears: int = _t(ctypes.c_int)
    mOdometerKM: float = _t(ctypes.c_float)
    mAntiLockActive: bool = _t(ctypes.c_bool)
    mLastOpponentCollisionIndex: int = _t(ctypes.c_int)
    mLastOpponentCollisionMagnitude: float = _t(ctypes.c_float)
    mBoostActive: bool = _t(ctypes.c_bool)
    mBoostAmount: float = _t(ctypes.c_float)

    # Motion & Device Related
    mOrientation: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mLocalVelocity: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mWorldVelocity: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mAngularVelocity: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mLocalAcceleration: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mWorldAcceleration: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)
    mExtentsCentre: list[float] = _t(ctypes.c_float * AMS2Constants.VEC_MAX)

    # Wheels / Tyres
    mTyreFlags: list[int] = _t(ctypes.c_uint * AMS2Constants.TYRE_MAX)
    mTerrain: list[int] = _t(ctypes.c_uint * AMS2Constants.TYRE_MAX)
    mTyreY: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreRPS: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreSlipSpeed: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)  # OBSOLETE
    mTyreTemp: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreGrip: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)  # OBSOLETE
    mTyreHeightAboveGround: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreLateralStiffness: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)  # OBSOLETE
    mTyreWear: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mBrakeDamage: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mSuspensionDamage: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mBrakeTempCelsius: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreTreadTemp: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreLayerTemp: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreCarcassTemp: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreRimTemp: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreInternalAirTemp: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)

    # Car Damage
    mCrashState: int = _t(ctypes.c_uint)
    mAeroDamage: float = _t(ctypes.c_float)
    mEngineDamage: float = _t(ctypes.c_float)

    # Weather
    mAmbientTemperature: float = _t(ctypes.c_float)
    mTrackTemperature: float = _t(ctypes.c_float)
    mRainDensity: float = _t(ctypes.c_float)
    mWindSpeed: float = _t(ctypes.c_float)
    mWindDirectionX: float = _t(ctypes.c_float)
    mWindDirectionY: float = _t(ctypes.c_float)
    mCloudBrightness: float = _t(ctypes.c_float)

    # PCars2 additions start, version 8
    # Sequence Number to help slightly with data integrity reads
    mSequenceNumber: int = _t(ctypes.c_uint)

    # Additional car variables
    mWheelLocalPositionY: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mSuspensionTravel: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mSuspensionVelocity: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mAirPressure: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mEngineSpeed: float = _t(ctypes.c_float)
    mEngineTorque: float = _t(ctypes.c_float)
    mWings: list[float] = _t(ctypes.c_float * 2)
    mHandBrake: float = _t(ctypes.c_float)

    # Additional race variables
    mCurrentSector1Times: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mCurrentSector2Times: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mCurrentSector3Times: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mFastestSector1Times: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mFastestSector2Times: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mFastestSector3Times: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mFastestLapTimes: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mLastLapTimes: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mLapsInvalidated: list[bool] = _t(ctypes.c_bool * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mRaceStates: list[int] = _t(ctypes.c_uint * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mPitModes: list[int] = _t(ctypes.c_uint * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mOrientations: list[list[float]] = _t((ctypes.c_float * AMS2Constants.VEC_MAX) * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mSpeeds: list[float] = _t(ctypes.c_float * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mCarNames: list[bytes] = _t((ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX) * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mCarClassNames: list[bytes] = _t((ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX) * AMS2Constants.STORED_PARTICIPANTS_MAX)

    # Additional race variables
    mEnforcedPitStopLap: int = _t(ctypes.c_int)
    mTranslatedTrackLocation: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)
    mTranslatedTrackVariation: bytes = _t(ctypes.c_char * AMS2Constants.STRING_LENGTH_MAX)
    mBrakeBias: float = _t(ctypes.c_float)
    mTurboBoostPressure: float = _t(ctypes.c_float)
    mTyreCompound: list[bytes] = _t((ctypes.c_char * AMS2Constants.TYRE_COMPOUND_NAME_LENGTH_MAX) * AMS2Constants.TYRE_MAX)
    mPitSchedules: list[int] = _t(ctypes.c_uint * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mHighestFlagColours: list[int] = _t(ctypes.c_uint * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mHighestFlagReasons: list[int] = _t(ctypes.c_uint * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mNationalities: list[int] = _t(ctypes.c_uint * AMS2Constants.STORED_PARTICIPANTS_MAX)
    mSnowDensity: float = _t(ctypes.c_float)

    # AMS2 Additions (v10...)
    # Session info
    mSessionDuration: float = _t(ctypes.c_float)
    mSessionAdditionalLaps: int = _t(ctypes.c_int)

    # Tyres
    mTyreTempLeft: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreTempCenter: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)
    mTyreTempRight: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)

    # DRS
    mDrsState: int = _t(ctypes.c_uint)

    # Suspension
    mRideHeight: list[float] = _t(ctypes.c_float * AMS2Constants.TYRE_MAX)

    # Input
    mJoyPad0: int = _t(ctypes.c_uint)
    mDPad: int = _t(ctypes.c_uint)

    mAntiLockSetting: int = _t(ctypes.c_int)
    mTractionControlSetting: int = _t(ctypes.c_int)

    # ERS
    mErsDeploymentMode: int = _t(ctypes.c_int)
    mErsAutoModeEnabled: bool = _t(ctypes.c_bool)

    # Clutch State & Damage
    mClutchTemp: float = _t(ctypes.c_float)
    mClutchWear: float = _t(ctypes.c_float)
    mClutchOverheated: bool = _t(ctypes.c_bool)
    mClutchSlipping: bool = _t(ctypes.c_bool)

    mYellowFlagState: int = _t(ctypes.c_int)

    mSessionIsPrivate: bool = _t(ctypes.c_bool)
    mLaunchStage: int = _t(ctypes.c_int)
