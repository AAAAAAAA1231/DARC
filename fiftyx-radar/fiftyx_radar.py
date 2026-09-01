"""PyInstaller entrypoint: python fiftyx_radar.py / FiftyXRadar.exe"""

from radar.__main__ import run

if __name__ == "__main__":
    raise SystemExit(run())
