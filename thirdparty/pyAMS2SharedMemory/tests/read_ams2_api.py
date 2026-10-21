"""
Read AMS2 shared memory data
"""

from __future__ import annotations

import sys
from time import sleep

sys.path.append(__file__.split("pyAMS2SharedMemory")[0])
from pyAMS2SharedMemory import ams2_data, ams2_mmap


def main():
    # Map shared memory (wait until game is running)
    info = ams2_mmap.MMapControl(ams2_data.AMS2Constants.MM_SHARED_MEMORY_NAME, ams2_data.SharedMemory)
    while True:
        try:
            info.create(0)
            break
        except (FileNotFoundError, ValueError):
            print("waiting for game...")
            sleep(1)

    # Print data
    try:
        while True:
            info.update()
            data = info.data
            if data.mSequenceNumber % 2:  # data being written
                continue
            print(
                f"\rstate:{data.mGameState} session:{data.mSessionState} "
                f"speed:{data.mSpeed:>6.1f}m/s rpm:{data.mRpm:>7.0f} "
                f"gear:{data.mGear:>2} fuel:{data.mFuelLevel * data.mFuelCapacity:>6.1f}L",
                end="",
            )
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        info.close()


if __name__ == "__main__":
    main()
