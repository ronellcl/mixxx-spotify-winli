# -*- coding: utf-8 -*-
"""
macOS Spotify controller using AppleScript (osascript).

This is the original backend from the repo. It drives the official
Spotify.app through its AppleScript dictionary. macOS only.
"""

import subprocess

from .base import BaseSpotifyController, SpotifyControllerError

#: AppleScript commands map to a stable minimal interface.
APPLE_SCRIPT_BUSY = "osascript is not installed or Spotify not running"


def _spotify(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", f'tell application "Spotify" to {script}'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SpotifyControllerError(
            result.stderr.strip() or "osascript failed"
        )
    return result.stdout.strip()


class MacSpotifyController(BaseSpotifyController):
    name = "macos"

    def play(self):
        _spotify("play")

    def pause(self):
        _spotify("pause")

    def playpause(self):
        _spotify("playpause")

    def cue(self):
        _spotify("pause")
        _spotify("set player position to 0")

    def seek(self, position: float):
        _spotify(f"set player position to {float(position)}")

    def volume(self, volume: int):
        volume = max(0, min(100, int(volume)))
        _spotify(f"set sound volume to {volume}")

    def get_volume(self) -> int:
        return int(_spotify("get sound volume"))

    def status(self) -> str:
        state = _spotify("get player state")
        position = float(_spotify("get player position"))
        duration_ms = int(_spotify("get duration of current track"))
        title = _spotify("get name of current track")
        artist = _spotify("get artist of current track")
        return (
            f"{artist} - {title}\n"
            f"{position:.1f} / {duration_ms / 1000.0:.1f} sec\n"
            f"{state}"
        )

    def next(self):
        _spotify("next track")

    def previous(self):
        _spotify("previous track")
