# -*- coding: utf-8 -*-
"""
Linux Spotify controller using D-Bus MPRIS.

The Spotify desktop app on Linux exposes the standard MPRIS2 interfaces
over the session D-Bus, which provide offline (no Web API / OAuth) control.

Uses dbus-python (system package python3-dbus) which vendors its own dbus
glib bindings. Install with:
    sudo apt-get install python3-dbus   (Debian/Ubuntu)
    sudo dnf install python3-dbus       (Fedora)
    ...or  pip install dbus-python
"""

from .base import BaseSpotifyController, SpotifyControllerError

MPRIS_BUS = "org.mpris.MediaPlayer2.spotify"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"


class LinuxSpotifyController(BaseSpotifyController):
    name = "linux"

    def __init__(self):
        try:
            import dbus
        except ImportError as exc:
            raise SpotifyControllerError(
                "dbus-python is required for Linux.\n"
                "Install it with:  python -m pip install dbus-python"
            ) from exc

        self._dbus = dbus
        self._bus = None
        self._player = None
        self._props = None
        self._connect()

    def _connect(self):
        try:
            bus = self._dbus.SessionBus()
            obj = bus.get_object(MPRIS_BUS, MPRIS_PATH)
            self._bus = bus
            self._player = self._dbus.Interface(
                obj, dbus_interface=PLAYER_IFACE
            )
            self._props = self._dbus.Interface(
                obj, dbus_interface=PROPS_IFACE
            )
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(
                "Could not connect to Spotify over D-Bus. "
                "Is the Spotify desktop app running?\n"
                f"Detail: {exc}"
            )

    def _get(self, name):
        try:
            return self._props.Get(PLAYER_IFACE, name)
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def _set(self, name, value):
        try:
            self._props.Set(PLAYER_IFACE, name, value)
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    # -- transport ------------------------------------------------------

    def play(self):
        try:
            self._player.Play()
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def pause(self):
        try:
            self._player.Pause()
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def playpause(self):
        try:
            self._player.PlayPause()
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def cue(self):
        """Pause and jump to the beginning of the current track."""
        try:
            self._player.Pause()
            meta = self._get("Metadata")
            track_id = meta.get("mpris:trackid", "/")
            if track_id:
                # SetPosition takes (trackid o, position x in microseconds).
                self._player.SetPosition(track_id, 0, dbus_interface=PLAYER_IFACE)
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def seek(self, position: float):
        # MPRIS Seek takes a relative offset in microseconds, not absolute.
        # Use SetPosition to jump absolutely.
        try:
            meta = self._get("Metadata")
            track_id = meta.get("mpris:trackid", "/")
            if track_id:
                self._player.SetPosition(track_id, int(position * 1_000_000))
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def volume(self, volume: int):
        volume = max(0, min(100, int(volume)))
        self._set("Volume", self._dbus.Double(volume / 100.0))

    def get_volume(self) -> int:
        try:
            vol = float(self._get("Volume"))
        except (SpotifyControllerError, TypeError):
            return -1
        return round(max(0.0, min(1.0, vol)) * 100.0)

    def status(self) -> str:
        try:
            status = str(self._get("PlaybackStatus"))
            position_us = int(self._get("Position")) if self._get("CanSeek") else 0
            meta = self._get("Metadata")
        except (SpotifyControllerError, self._dbus.DBusException) as exc:
            raise SpotifyControllerError(str(exc))

        title = meta.get("xesam:title", "?")
        artist = meta.get("xesam:artist")
        if isinstance(artist, (list, tuple)):
            artist = ", ".join(str(a) for a in artist)
        artist = str(artist or "?")

        duration_us = meta.get("mpris:length", 0)
        try:
            duration_us = int(duration_us)
        except (TypeError, ValueError):
            duration_us = 0

        def fmt_us(us):
            return f"{us / 1_000_000.0:.1f}"

        return (
            f"{artist} - {title}\n"
            f"{fmt_us(position_us)} / {fmt_us(duration_us)} sec\n"
            f"{status.lower()}"
        )

    def next(self):
        try:
            self._player.Next()
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))

    def previous(self):
        try:
            self._player.Previous()
        except self._dbus.DBusException as exc:
            raise SpotifyControllerError(str(exc))
