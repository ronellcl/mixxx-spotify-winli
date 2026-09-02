# -*- coding: utf-8 -*-
"""
Windows Spotify controller using libspotifyctl (SMTC).

libspotifyctl talks to the official Spotify desktop app through the Windows
System Media Transport Controls (SMTC) and Core Audio — fully offline, no
Spotify Web API, no OAuth, no network calls.

Install with:
    pip install libspotifyctl

Windows only (Windows 10 1809+/11, x64, CPython 3.9+).
"""

import time

from .base import BaseSpotifyController, SpotifyControllerError


class WindowsSpotifyController(BaseSpotifyController):
    name = "windows"

    def __init__(self):
        try:
            import libspotifyctl
        except ImportError as exc:
            raise SpotifyControllerError(
                "libspotifyctl is required for Windows.\n"
                "Install it with:  python -m pip install libspotifyctl"
            ) from exc

        self._lib = libspotifyctl
        self._client = None
        self._ensure_started()

    def _ensure_started(self):
        if self._client is None:
            self._client = self._lib.SpotifyClient()
            self._client.start()

    # -- transport ------------------------------------------------------

    def play(self):
        self._ensure_started()
        self._client.play()

    def pause(self):
        self._ensure_started()
        self._client.pause()

    def playpause(self):
        self._ensure_started()
        self._client.send_command(self._lib.AppCommand.PLAY_PAUSE)

    def cue(self):
        """Pause and jump to the beginning of the current track."""
        self._ensure_started()
        self._client.pause()
        self._client.seek_ms(0)

    def seek(self, position: float):
        self._ensure_started()
        self._client.seek_ms(int(position * 1000))

    def volume(self, volume: int):
        self._ensure_started()
        volume = max(0, min(100, int(volume)))
        try:
            self._client.app_volume = volume / 100.0
        except Exception as exc:
            # The per-app audio session only exists after Spotify first
            # outputs sound; ignore gracefully if it is not available yet.
            raise SpotifyControllerError(f"Failed to set volume: {exc}")

    def get_volume(self) -> int:
        self._ensure_started()
        vol = self._client.app_volume
        if vol < 0:
            return -1
        return round(vol * 100.0)

    def status(self) -> str:
        self._ensure_started()
        state = self._client.latest_state()
        pos = state.position_ms / 1000.0
        dur = state.duration_ms / 1000.0
        status_name = getattr(state.status, "name", "?")
        return (
            f"{state.artist} - {state.title}\n"
            f"{pos:.1f} / {dur:.1f} sec\n"
            f"{status_name.lower()}"
        )

    def next(self):
        self._ensure_started()
        self._client.next()

    def previous(self):
        self._ensure_started()
        self._client.previous()

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
