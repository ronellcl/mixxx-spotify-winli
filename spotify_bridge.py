#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spotify_bridge.py

Cross-platform Spotify bridge for Mixxx.

Two modes:
  1) Listener mode (default):
       ./spotify_bridge.py
     Listens to a virtual MIDI port "SpotifyMixxx" and translates commands
     from Mixxx into local Spotify playback commands (the backend depends on
     the OS: AppleScript on macOS, SMTC on Windows, D-Bus MPRIS on Linux).

  2) Manual CLI mode:
       ./spotify_bridge.py play
       ./spotify_bridge.py pause
       ./spotify_bridge.py cue
       ./spotify_bridge.py volume 75
       ./spotify_bridge.py seek 30
       ./spotify_bridge.py status
       ./spotify_bridge.py next
       ./spotify_bridge.py previous

Dependencies:
    python3 -m pip install python-rtmidi      (all platforms)
    python3 -m pip install libspotifyctl      (Windows)
    python3 -m pip install dbus-python        (Linux)

MIDI protocol expected from SpotifyMixxx.js:
    Note 0x10 velocity > 0  -> PLAY
    Note 0x11 velocity > 0  -> PAUSE
    Note 0x12 velocity > 0  -> CUE (pause + seek 0)
    CC   0x20 value 0..127  -> Spotify volume 0..100
"""

import platform
import queue
import sys
import threading
import time


MIDI_PORT_NAME = "SpotifyMixxx"

NOTE_PLAY = 0x10
NOTE_PAUSE = 0x11
NOTE_CUE = 0x12
CC_VOLUME = 0x20


def get_controller():
    """Return the backend suited to the current OS."""
    system = platform.system().lower()

    if system == "windows":
        from spotify_backends.windows import WindowsSpotifyController
        return WindowsSpotifyController()

    if system == "linux":
        from spotify_backends.linux import LinuxSpotifyController
        return LinuxSpotifyController()

    if system == "darwin":
        from spotify_backends.macos import MacSpotifyController
        return MacSpotifyController()

    raise RuntimeError(f"Unsupported platform: {system}")


class MidiSpotifyBridge:
    """
    MIDI callback stays lightweight. Transport commands are queued.
    Volume messages are coalesced so dragging a Mixxx gain knob cannot
    create a large backlog of Spotify commands.
    """

    def __init__(self, controller):
        self.controller = controller
        self.commands = queue.Queue()
        self._volume_lock = threading.Lock()
        self._pending_volume = None
        self._running = True

    def enqueue_transport(self, command: str):
        self.commands.put(command)

    def set_pending_volume(self, value: int):
        with self._volume_lock:
            self._pending_volume = value

    def take_pending_volume(self):
        with self._volume_lock:
            value = self._pending_volume
            self._pending_volume = None
            return value

    def worker(self):
        last_volume = None

        while self._running:
            # Transport has priority over volume.
            try:
                command = self.commands.get(timeout=0.03)
            except queue.Empty:
                command = None

            try:
                if command == "play":
                    self.controller.play()
                elif command == "pause":
                    self.controller.pause()
                elif command == "cue":
                    self.controller.cue()

                volume = self.take_pending_volume()
                if volume is not None and volume != last_volume:
                    self.controller.volume(volume)
                    last_volume = volume

            except Exception as exc:
                print(
                    f"[SpotifyMixxx] Spotify command failed: {exc}",
                    file=sys.stderr,
                )

    def midi_callback(self, event, _data=None):
        message, _delta_time = event
        if len(message) < 3:
            return

        status, data1, data2 = message[:3]
        message_type = status & 0xF0

        # Note On; ignore velocity 0 (equivalent to Note Off).
        if message_type == 0x90 and data2 > 0:
            if data1 == NOTE_PLAY:
                print("[SpotifyMixxx] MIDI: PLAY", flush=True)
                self.enqueue_transport("play")
            elif data1 == NOTE_PAUSE:
                print("[SpotifyMixxx] MIDI: PAUSE", flush=True)
                self.enqueue_transport("pause")
            elif data1 == NOTE_CUE:
                print("[SpotifyMixxx] MIDI: CUE", flush=True)
                self.enqueue_transport("cue")

        elif message_type == 0xB0 and data1 == CC_VOLUME:
            volume = round((data2 / 127.0) * 100.0)
            print(
                f"[SpotifyMixxx] MIDI: VOLUME cc={data2} -> {volume}",
                flush=True,
            )
            self.set_pending_volume(volume)


def find_port(midi_in, wanted: str):
    ports = midi_in.get_ports()

    # Prefer an exact-ish suffix/substring match. The virtual MIDI port name
    # differs per platform:
    #   macOS:  "IAC Driver SpotifyMixxx"
    #   Windows:"loopMIDI Port"  (renamed to SpotifyMixxx)
    #   Linux:  ALSA virtual port
    matches = [(i, name) for i, name in enumerate(ports) if wanted.lower() in name.lower()]

    if not matches:
        print(f'Could not find MIDI input containing "{wanted}".', file=sys.stderr)
        print("Available MIDI inputs:", file=sys.stderr)
        for i, name in enumerate(ports):
            print(f"  {i}: {name}", file=sys.stderr)
        return None

    return matches[0]


def listen():
    try:
        import rtmidi
    except ImportError:
        print(
            "python-rtmidi is required for listener mode.\n"
            "Install it with:\n"
            "  python3 -m pip install python-rtmidi",
            file=sys.stderr,
        )
        sys.exit(2)

    controller = get_controller()
    print(f"[SpotifyMixxx] Spotify backend: {controller.name}")

    midi_in = rtmidi.MidiIn()
    match = find_port(midi_in, MIDI_PORT_NAME)
    if match is None:
        sys.exit(3)

    port_index, port_name = match
    midi_in.open_port(port_index)

    bridge = MidiSpotifyBridge(controller)
    worker = threading.Thread(target=bridge.worker, daemon=True)
    worker.start()

    midi_in.set_callback(bridge.midi_callback)

    print(f'[SpotifyMixxx] Listening on MIDI input: "{port_name}"')
    print("[SpotifyMixxx] Ctrl-C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SpotifyMixxx] Stopping.")
    finally:
        bridge._running = False
        midi_in.cancel_callback()
        midi_in.close_port()
        controller.close()


def usage():
    print(
        """Usage:
  spotify_bridge.py                  # listen on SpotifyMixxx MIDI
  spotify_bridge.py listen
  spotify_bridge.py play
  spotify_bridge.py pause
  spotify_bridge.py playpause
  spotify_bridge.py cue
  spotify_bridge.py seek <seconds>
  spotify_bridge.py volume <0-100>
  spotify_bridge.py getvolume
  spotify_bridge.py status
  spotify_bridge.py next
  spotify_bridge.py previous
"""
    )


def main():
    if len(sys.argv) == 1 or sys.argv[1].lower() == "listen":
        listen()
        return

    command = sys.argv[1].lower()

    try:
        controller = get_controller()

        if command == "play":
            controller.play()

        elif command == "pause":
            controller.pause()

        elif command == "playpause":
            controller.playpause()

        elif command == "cue":
            controller.cue()

        elif command == "seek":
            if len(sys.argv) != 3:
                raise ValueError("seek requires position in seconds")
            controller.seek(float(sys.argv[2]))

        elif command == "volume":
            if len(sys.argv) != 3:
                raise ValueError("volume requires a value from 0 to 100")
            controller.volume(int(sys.argv[2]))

        elif command == "getvolume":
            print(controller.get_volume())

        elif command == "status":
            print(controller.status())

        elif command == "next":
            controller.next()

        elif command == "previous":
            controller.previous()

        else:
            usage()
            sys.exit(1)

        controller.close()

    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
