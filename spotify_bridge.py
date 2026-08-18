#!/usr/bin/env python3
"""
spotify_bridge.py

Small macOS Spotify bridge.

Two modes:
  1) Listener mode (default):
       ./spotify_bridge.py
     Listens to the IAC MIDI port "SpotifyMixxx" and translates commands
     from Mixxx into local Spotify.app AppleScript commands.

  2) Manual CLI mode:
       ./spotify_bridge.py play
       ./spotify_bridge.py pause
       ./spotify_bridge.py cue
       ./spotify_bridge.py volume 75
       ./spotify_bridge.py seek 30
       ./spotify_bridge.py status
       ./spotify_bridge.py next
       ./spotify_bridge.py previous

Dependency:
    python3 -m pip install python-rtmidi

MIDI protocol expected from SpotifyMixxx.js:
    Note 0x10 velocity > 0  -> PLAY
    Note 0x11 velocity > 0  -> PAUSE
    Note 0x12 velocity > 0  -> CUE (pause + seek 0)
    CC   0x20 value 0..127  -> Spotify volume 0..100
"""

import queue
import subprocess
import sys
import threading
import time

MIDI_PORT_NAME = "SpotifyMixxx"

NOTE_PLAY = 0x10
NOTE_PAUSE = 0x11
NOTE_CUE = 0x12
CC_VOLUME = 0x20


def spotify(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", f'tell application "Spotify" to {script}'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "osascript failed")
    return result.stdout.strip()


def do_play():
    spotify("play")


def do_pause():
    spotify("pause")


def do_cue():
    spotify("pause")
    spotify("set player position to 0")


def do_volume(volume: int):
    volume = max(0, min(100, int(volume)))
    spotify(f"set sound volume to {volume}")


def do_seek(position: float):
    spotify(f"set player position to {float(position)}")


def print_status():
    state = spotify("get player state")
    position = float(spotify("get player position"))
    duration_ms = int(spotify("get duration of current track"))
    title = spotify("get name of current track")
    artist = spotify("get artist of current track")
    print(f"{artist} - {title}")
    print(f"{position:.1f} / {duration_ms / 1000.0:.1f} sec")
    print(state)


class MidiSpotifyBridge:
    """
    MIDI callback stays lightweight. Transport commands are queued.
    Volume messages are coalesced so dragging a Mixxx gain knob cannot
    create a large backlog of osascript processes.
    """

    def __init__(self):
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
                    do_play()
                elif command == "pause":
                    do_pause()
                elif command == "cue":
                    do_cue()

                volume = self.take_pending_volume()
                if volume is not None and volume != last_volume:
                    do_volume(volume)
                    last_volume = volume

            except Exception as exc:
                print(f"[SpotifyMixxx] Spotify command failed: {exc}", file=sys.stderr)

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

    # Prefer an exact-ish suffix/substring match because macOS commonly
    # exposes IAC ports as "IAC Driver SpotifyMixxx".
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

    midi_in = rtmidi.MidiIn()
    match = find_port(midi_in, MIDI_PORT_NAME)
    if match is None:
        sys.exit(3)

    port_index, port_name = match
    midi_in.open_port(port_index)

    bridge = MidiSpotifyBridge()
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
        if command == "play":
            do_play()

        elif command == "pause":
            do_pause()

        elif command == "playpause":
            spotify("playpause")

        elif command == "cue":
            do_cue()

        elif command == "seek":
            if len(sys.argv) != 3:
                raise ValueError("seek requires position in seconds")
            do_seek(float(sys.argv[2]))

        elif command == "volume":
            if len(sys.argv) != 3:
                raise ValueError("volume requires a value from 0 to 100")
            do_volume(int(sys.argv[2]))

        elif command == "getvolume":
            print(spotify("get sound volume"))

        elif command == "status":
            print_status()

        elif command == "next":
            spotify("next track")

        elif command == "previous":
            spotify("previous track")

        else:
            usage()
            sys.exit(1)

    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
