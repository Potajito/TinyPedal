"""
Test AMS2 Memory Map Control
"""

from __future__ import annotations

import logging
import sys

sys.path.append(__file__.split("pyAMS2SharedMemory")[0])
from pyAMS2SharedMemory import ams2_data, ams2_mmap


def test_api():
    # Add logger
    logger = logging.getLogger(__name__)
    test_handler = logging.StreamHandler()
    logger.setLevel(logging.INFO)
    logger.addHandler(test_handler)
    logger.info(__doc__)

    # Test run
    SEPARATOR = "=" * 50
    print("Test API - Direct Access")
    info = ams2_mmap.MMapControl(ams2_data.AMS2Constants.MM_SHARED_MEMORY_NAME, ams2_data.SharedMemory)
    info.create(1)
    info.update()

    print(SEPARATOR)
    print("Test API - Close")
    info.close()

    print(SEPARATOR)
    print("Test API - Copy Access")
    info.create(0)
    info.update()

    print(SEPARATOR)
    print("Test API - Read")
    version = info.data.mVersion
    num_participants = info.data.mNumParticipants
    track = info.data.mTrackLocation
    vehicle = info.data.mCarName
    print(f"version: {version if version else 'not running'}")
    print(f"total participants: {num_participants if version else 'not running'}")
    print(f"track name: {track if version else 'not running'}")
    print(f"vehicle name: {vehicle if version else 'not running'}")

    print(SEPARATOR)
    info.close()


if __name__ == "__main__":
    test_api()
