# -*- coding: utf-8 -*-
"""
Common interface for Spotify-controller backends.

Each backend wraps OS-specific ways of talking to the local Spotify desktop
app. The bridge talks to these through this base interface, keeping
OS-specific code out of spotify_bridge.py.
"""


class SpotifyControllerError(RuntimeError):
    pass


class BaseSpotifyController:
    """Abstract base class for OS-specific Spotify controllers."""

    #: Human-readable name of the backend (for logs / help).
    name = "base"

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def playpause(self) -> None:
        raise NotImplementedError

    def cue(self) -> None:
        """Pause and jump to the beginning of the current track."""
        raise NotImplementedError

    def seek(self, position: float) -> None:
        """Seek to ``position`` seconds within the current track."""
        raise NotImplementedError

    def volume(self, volume: int) -> None:
        """Set Spotify app volume to ``volume`` (0..100)."""
        raise NotImplementedError

    def get_volume(self) -> int:
        raise NotImplementedError

    def status(self) -> str:
        """Return a human-readable one/multi-line status string."""
        raise NotImplementedError

    def next(self) -> None:
        raise NotImplementedError

    def previous(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass
