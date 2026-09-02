# Mixxx Spotify Proxy (multi-platform)

A small, unofficial bridge that makes a normal Mixxx deck behave like a **proxy deck for the official Spotify desktop app**.

Supported platforms:

- **Windows** (via `libspotifyctl`, SMTC + Core Audio)
- **macOS** (via AppleScript)
- **Linux** (via D-Bus MPRIS)

It is intended for the occasional situation where you are DJing from local files in Mixxx and someone requests a song that you only have on Spotify.

This project **does not download, decrypt, rip, or expose Spotify audio files**. Spotify continues to play the audio in the official Spotify app. Mixxx receives that audio through a virtual audio input and mirrors normal deck controls to it.

## What it feels like when it is working

You find a song manually in Spotify, then load a special 10-second file called `spotify-silence.mp3` into the free Mixxx deck.

From that point:

| Mixxx control | What happens |
|---|---|
| PLAY | Spotify plays |
| Pause / PLAY off | Spotify pauses |
| CUE | Spotify pauses and jumps to the beginning |
| Deck gain | Spotify app volume changes |
| Channel fader | Mixxx AUX1 volume follows the deck |
| PFL | AUX1 PFL follows the deck |
| FX assignment | The same Mixxx FX unit is routed to AUX1 |
| Crossfader, Spotify on Deck 1 | AUX1 is assigned to the left side |
| Crossfader, Spotify on Deck 2 | AUX1 is assigned to the right side |

The command may come from the Mixxx GUI, a keyboard shortcut, or your normal DJ controller mapping. The Spotify script watches Mixxx's internal Deck 1 / Deck 2 controls, so it does not need to modify your physical controller mapping.

When the sentinel track is removed, the Spotify proxy turns itself off and AUX1 is disabled.

---

# Architecture

```
                            CONTROL

Mixxx Deck 1 / Deck 2
        |
        v
SpotifyMixxx.js
        |
        | MIDI (virtual port "SpotifyMixxx")
        v
spotify_bridge.py
        |
        | OS backend
        |   macOS:   AppleScript
        |   Windows: libspotifyctl (SMTC / Core Audio)
        |   Linux:   D-Bus MPRIS
        v
official Spotify app


                             AUDIO

official Spotify app
        |
        v
virtual audio device (mac: BlackHole / win: VB-Cable /
                        linux: PulseAudio/PipeWire monitor)
        |
        v
Mixxx AUX1
        |
        v
PFL / FX / channel fader / crossfader
        |
        v
Mixxx Master
```

The Mixxx-side logic (`SpotifyMixxx.js`) and the MIDI XML mapping are **identical across all three platforms**. Only the Spotify control backend and the virtual MIDI/audio plumbing differ.

---

# Requirements

You need:

- One of: Windows 10/11, macOS, or Linux
- Mixxx
- the official Spotify desktop application
- a Spotify account that can play music in the desktop app
- Python 3
- A virtual MIDI port named `SpotifyMixxx` (platform-specific tool, below)
- A virtual audio input (platform-specific tool, below)
- `ffmpeg` once, to create the small sentinel MP3

A DJ controller is optional. This also works with only the Mixxx GUI.

---

# Platform-specific components

Use only the sections relevant to your OS.

## Windows

| Component | Tool | Notes |
|---|---|---|
| Spotify control | `libspotifyctl` | offline, no OAuth — `pip install libspotifyctl` |
| Virtual MIDI | [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) | free |
| Virtual audio | [VB-Audio Cable](https://vb-audio.com/Cable/) | free (donation-ware) |

### Windows: virtual MIDI (loopMIDI)

1. Download and run loopMIDI from https://www.tobias-erichsen.de/software/loopmidi.html
2. Click the `+` button in the bottom-left to add a port.
3. Name it `SpotifyMixxx` (exactly).
4. Keep loopMIDI running (it minimizes to the tray).
5. Restart Mixxx so it picks up the new port.

### Windows: virtual audio (VB-Audio Cable)

1. Download and install VB-Audio Cable from https://vb-audio.com/Cable/ (run setup as Administrator, reboot if requested).
2. In **Windows Settings → System → Sound → Volume mixer**, change the output device for **Spotify only** to `CABLE Input (VB-Cable)`.
3. In Mixxx **Preferences → Sound Hardware → Input**, set:
   ```
   Auxiliary 1 -> CABLE Output (VB-Cable) -> Channels 1-2
   ```
   Keep your Mixxx master/headphones outputs on your real DJ interface.
4. Apply and verify Spotify audio arrives on AUX1 before continuing.

> Windows Sound settings may list the device as "CABLE Input / CABLE Output".

---

## macOS

| Component | Tool | Notes |
|---|---|---|
| Spotify control | AppleScript | built-in |
| Virtual MIDI | IAC Driver | built-in |
| Virtual audio | [BlackHole](https://github.com/ExistentialAudio/BlackHole) | free (Homebrew `brew install blackhole-2ch`) |

### macOS: virtual MIDI (IAC bus)

IAC Driver is built-in. See the original project notes in the "Installation walkthrough" for full steps. In short:

1. Open `Applications → Utilities → Audio MIDI Setup`
2. `Window → Show MIDI Studio`
3. Double-click **IAC Driver**, enable **Device is online**
4. Under **Ports**, click `+`, rename the bus to `SpotifyMixxx`
5. Restart Mixxx.

### macOS: virtual audio (BlackHole)

1. `brew install blackhole-2ch` (or install the package from the BlackHole project).
2. Set **BlackHole 2ch** as the macOS system output (Spotify follows the system output).
3. In Mixxx **Preferences → Sound Hardware → Input**, set:
   ```
   Auxiliary 1 -> BlackHole 2ch -> Channels 1-2
   ```
4. You will not hear Spotify through the speakers until AUX1 is enabled in Mixxx (expected).

---

## Linux

| Component | Tool | Notes |
|---|---|---|
| Spotify control | D-Bus MPRIS | built into the Spotify desktop app |
| Virtual MIDI | ALSA virtual ports (`snd-virmidi`) | built into the kernel |
| Virtual audio | PulseAudio / PipeWire monitor / null-sink | built-in |

### Linux: virtual MIDI (ALSA)

The `snd-virmidi` kernel module provides virtual raw MIDI devices:

```bash
sudo modprobe snd-virmidi
```

This creates raw MIDI ports along the lines of `VirMIDI 1-0` / `Midi Through Port-0`, which Mixxx can use. To create a loopback so Mixxx's output reaches the Python bridge, connect the ports with `aconnect`:

```bash
# List available ALSA MIDI ports
aconnect -l
```

Mixxx writes to one of the `Midi Through Port-X` outputs; the bridge listens on the matching input. On systems with PipeWire, the newer `pw-loopback`/MIDI bridging may also be available.

A simpler alternative that many users prefer is to create a virtual port using `rtmidi` itself from the bridge (see below), but the common documented path is ALSA virtual ports.

### Linux: virtual audio (PulseAudio / PipeWire null-sink)

Create a null sink that Spotify outputs to, and point Mixxx at its monitor:

```bash
# PulseAudio
pactl load-module module-null-sink sink_name=SpotifyMonitor sink_properties=device.description=SpotifyMonitor
```

```bash
# PipeWire (pipewire-pulse)
pactl load-module module-null-sink sink_name=SpotifyMonitor sink_properties=device.description=SpotifyMonitor
```

Route Spotify's output to `SpotifyMonitor` (e.g. with `pavucontrol` → Playback tab → set Spotify's device to *SpotifyMonitor*).

In Mixxx **Preferences → Sound Hardware → Input**, set:

```
Auxiliary 1 -> SpotifyMonitor.monitor -> Channels 1-2
```

If the sink does not persist across reboots, add the `load-module` line to your PulseAudio/PipeWire config (e.g. `~/.config/pulse/default.pa` for PulseAudio).

---

# Python bridge

The Python bridge is the same script for all platforms; it auto-detects the OS and loads the correct backend.

## Install Python 3 if necessary

Check:

```bash
python3 --version     # macOS / Linux
python --version      # Windows
```

If you get something like `Python 3.12.4`, you are ready.

## Open the project directory

```bash
cd path/to/mixxx-spotify-winli
```

You should have at least:

```text
README.md
SpotifyMixxx.js
SpotifyMixxx.midi.xml
spotify_bridge.py
spotify_backends/
requirements.txt
```

## Create a Python virtual environment

```bash
python3 -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat
```

Install the base dependency:

```bash
python -m pip install -r requirements.txt
```

Then install your platform's backend:

```bash
# Windows
python -m pip install libspotifyctl

# Linux
python -m pip install dbus-python
```

## Test the Python bridge manually

While the virtual environment is active:

```bash
python spotify_bridge.py status
```

If Spotify has a track selected, you should see something similar to:

```text
Artist - Track
26.8 / 201.4 sec
paused
```

Try:

```bash
python spotify_bridge.py play
python spotify_bridge.py pause
python spotify_bridge.py cue
python spotify_bridge.py volume 50
python spotify_bridge.py seek 30
```

`cue` pauses Spotify and moves the current track back to the beginning.

If these work, the Python → Spotify part is ready.

## Run the bridge in MIDI listener mode

Simply run:

```bash
python spotify_bridge.py
```

You should see something like:

```text
[SpotifyMixxx] Spotify backend: windows   # or macos / linux
[SpotifyMixxx] Listening on MIDI input: "SpotifyMixxx"
[SpotifyMixxx] Ctrl-C to stop.
```

Leave this terminal window running while you use the Spotify proxy.

When Mixxx later sends commands you will see messages such as:

```text
[SpotifyMixxx] MIDI: PLAY
[SpotifyMixxx] MIDI: PAUSE
[SpotifyMixxx] MIDI: CUE
[SpotifyMixxx] MIDI: VOLUME cc=127 -> 100
```

To stop the bridge, press `Control-C`.

---

# Install the Mixxx integration

The following is identical on all platforms.

## Find the Mixxx user controller/mapping directory

Open:

```text
Preferences -> Controllers
```

Click the button that opens the **User Mapping / User Preset Folder**. Do not modify Mixxx's built-in controller files.

Copy these two files from this repository into the Mixxx user controller folder:

```text
SpotifyMixxx.js
SpotifyMixxx.midi.xml
```

Restart Mixxx after copying them.

## Enable the `SpotifyMixxx` virtual controller

Open `Mixxx → Preferences → Controllers`. You should see your virtual MIDI device, e.g.:

```text
Windows:  loopMIDI Port
macOS:    IAC Driver SpotifyMixxx
Linux:    Midi Through Port-X / VirMIDI ...
```

Select it, then load/select the mapping:

```text
SpotifyMixxx
```

Make sure the controller/mapping is enabled.

This mapping intentionally contains no normal MIDI button mappings. Its purpose is to make Mixxx load `SpotifyMixxx.js` and give that JavaScript file access to the virtual MIDI output. Your existing physical DJ controller mapping remains unchanged.

---

# Create the sentinel track

## Install ffmpeg if necessary

```bash
ffmpeg -version
```

If not installed:
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Windows: download a build or use `winget install Gyan.FFmpeg`

## Create `spotify-silence.mp3`

```bash
ffmpeg \
  -f lavfi \
  -i "sine=frequency=1000:sample_rate=44100:duration=10" \
  -af "volume=-90dB" \
  -q:a 9 \
  -acodec libmp3lame \
  spotify-silence.mp3
```

This creates a 10-second 44.1 kHz MP3 containing an extremely quiet tone.

Why not absolute silence? Mixxx may spend longer analyzing completely silent files. The `-90 dB` tone is effectively inaudible but gives Mixxx immediate audio data.

The script identifies the sentinel by: approximately 10 seconds and 44100 Hz sample rate. It does **not** depend on a particular filesystem path.

## Import the sentinel into Mixxx

Move `spotify-silence.mp3` somewhere permanent in your music library, import it into Mixxx, and (recommended) add it to a crate called `Spotify` for fast loading.

---

# First end-to-end test

Before testing, verify:

1. Spotify desktop app is running.
2. A Spotify song is selected.
3. Spotify's audio is routed to your virtual audio input (VB-Cable / BlackHole / null-sink monitor).
4. Mixxx AUX1 input is that virtual audio input.
5. The `SpotifyMixxx` virtual MIDI port is enabled in Mixxx.
6. The `SpotifyMixxx` mapping is loaded.
7. The Python bridge is running: `python spotify_bridge.py`

## Load the proxy into Deck 1

In Mixxx, load `spotify-silence.mp3` into Deck 1. Within about 250 ms, `SpotifyMixxx.js` recognizes the sentinel and automatically:

- disables AutoDJ
- enables AUX1
- enables repeat on the short sentinel
- routes AUX1 to the left side of the crossfader
- mirrors the deck fader to AUX1
- mirrors PFL to AUX1
- mirrors FX assignments to AUX1

The script intentionally does **not** automatically re-enable AutoDJ later.

## Press PLAY

Press PLAY on Deck 1 (GUI, keyboard mapping, or DJ controller). The Python terminal should print `[SpotifyMixxx] MIDI: PLAY` and Spotify should begin playing. Press PLAY again to pause (`MIDI: PAUSE`).

## Test CUE

Press CUE on Deck 1. The bridge prints `[SpotifyMixxx] MIDI: CUE`; Spotify pauses and returns to the beginning.

## Test PFL

Turn on PFL for the proxy deck. The script mirrors that to `AUX1 PFL`, so you can preview through the Mixxx headphone path.

## Test the channel fader

Move the proxy deck's channel fader; it mirrors to `AUX1 volume`.

## Test the crossfader

- Sentinel in Deck 1 → `AUX1 -> LEFT`
- Sentinel in Deck 2 → `AUX1 -> RIGHT`

Spotify behaves as if its audio came from that deck.

## Test FX

Assign an FX unit to the proxy deck; the script routes that same FX unit to AUX1, so the real Spotify audio is processed by it.

---

# Normal party workflow

1. Someone requests a song you do not have locally.
2. Search for it in the normal Spotify app and select it.
3. In Mixxx, open the `Spotify` crate.
4. Load `spotify-silence.mp3` into whichever deck is free.
5. Use PFL normally.
6. Press PLAY normally.
7. Transition with the channel fader / FX / crossfader normally.
8. While Spotify is playing, prepare the next normal local Mixxx track.
9. Load a normal track over `spotify-silence.mp3` when finished.

When the sentinel disappears from the proxy deck, repeat is off, Spotify is paused, AUX1 is reset/disabled, and the deck returns to normal operation.

---

# If you accidentally load the sentinel into both decks

Only one Spotify source exists, so only one deck may control it. The script protects against loading the sentinel in both decks: the active proxy keeps ownership, the second sentinel is ignored, and if both are loaded when the script starts, Deck 1 wins.

---

# Troubleshooting

## Python says it cannot find `SpotifyMixxx`

```text
Could not find MIDI input containing "SpotifyMixxx"
```

- **Windows:** make sure loopMIDI is running and the port `SpotifyMixxx` exists.
- **macOS:** check Audio MIDI Setup → MIDI Studio → IAC Driver, port created and online.
- **Linux:** check `aconnect -l` for the virtual port, and that the bridge's MIDI input matches.

Restart the Python bridge after creating/renaming the port.

## Mixxx does not show the virtual MIDI device

Quit and restart Mixxx after creating the port. Then check `Preferences -> Controllers`.

## Python works manually but receives nothing from Mixxx

Look in the Mixxx log for `[SpotifyMixxx] initializing` and `[SpotifyMixxx] ready`. If the script is not loading:

- confirm both files are in the Mixxx user controller folder
- confirm `SpotifyMixxx.midi.xml` references `SpotifyMixxx.js`
- confirm the virtual MIDI device has the `SpotifyMixxx` mapping selected and enabled

## The backend fails to import

- **Windows:** `ModuleNotFoundError: libspotifyctl` → run `python -m pip install libspotifyctl`
- **Linux:** `ModuleNotFoundError: dbus` → run `python -m pip install dbus-python`
- **Windows/Linux status unknown:** the backend could not read Spotify state — make sure Spotify is running and has played audio at least once.

## Spotify is playing but you cannot hear it

Check the audio path in order:

```text
Spotify
 -> virtual audio out (VB-Cable / BlackHole / null-sink monitor)
 -> Mixxx Auxiliary 1
 -> Mixxx master
```

Temporarily enable AUX1 manually in Mixxx and check whether its meter moves.

## I can hear Spotify regardless of the crossfader

The script expects AUX1 to participate in Mixxx's main mix using `[Auxiliary1],main_mix` and sets `orientation = 0` for Deck 1 / `2` for Deck 2. Make sure you use the supplied `SpotifyMixxx.js`.

## Linux: `osc.Volume` doesn't change

Spotify may not expose a writeable `Volume` on all versions. The bridge handles this gracefully, but volume control depends on Spotify's MPRIS support; transport (play/pause/cue/seek/next/previous) always works.

## The sentinel takes a long time to load

Use the supplied 10-second / -90 dB sentinel recipe. Do not use long or absolute-silence files.

## Spotify volume stops at unity gain

This is intentional. Deck gain maps to Spotify's own 0–100 application volume; deck pregain above unity is clamped to 100. The channel fader remains handled through AUX1 in Mixxx.

---

# Files in this repository

```text
spotify_bridge.py
```

Auto-detects the OS and runs the bridge. Listens to the `SpotifyMixxx` virtual MIDI port and translates commands to the OS backend.

```text
spotify_backends/
  base.py       # common interface
  windows.py    # libspotifyctl (SMTC / Core Audio)
  macos.py      # AppleScript
  linux.py      # D-Bus MPRIS
```

OS-specific Spotify control backends.

```text
SpotifyMixxx.js
```

Mixxx-side logic (platform-independent). Detects the sentinel, watches Deck 1/2, mirrors routing to AUX1, and sends transport/volume over MIDI.

```text
SpotifyMixxx.midi.xml
```

Virtual-controller mapping whose main purpose is to load `SpotifyMixxx.js` for the virtual MIDI device.

```text
requirements.txt
```

Base dependency (`python-rtmidi`); platform backends are documented inside.

---

# MIDI protocol

The bridge intentionally uses a tiny private MIDI protocol:

```text
Note 16, velocity > 0  -> Spotify PLAY
Note 17, velocity > 0  -> Spotify PAUSE
Note 18, velocity > 0  -> Spotify CUE
CC 32, value 0..127    -> Spotify volume 0..100
```

This is only communication between `SpotifyMixxx.js` and `spotify_bridge.py`.

---

# Limitations

This is not native Spotify support in Mixxx. You do not get:

- Spotify waveform in Mixxx
- Spotify BPM/key analysis in the proxy deck
- beat sync against the Spotify track
- scratching
- hotcues for Spotify
- automatic Spotify search from Mixxx
- Spotify track metadata inside the proxy deck

The goal is deliberately smaller: make an occasional requested Spotify song easy to cue, monitor and transition inside an otherwise normal Mixxx set.

---

# Privacy and security

The bridge:

- listens only to a local MIDI device
- controls the local Spotify app using OS-native backends (AppleScript / SMTC / D-Bus)
- does not require Spotify API credentials
- does not require OAuth
- does not contain a Spotify password
- does not contact a custom server

Spotify authentication remains entirely inside the official Spotify application.

---

# Legal / service terms

This is an unofficial community project and is not affiliated with Spotify, Mixxx, Microsoft, Apple, or any virtual-audio/MIDI vendor.

It does not bypass Spotify DRM or create downloadable copies of Spotify tracks.

You are responsible for complying with Spotify's terms and any music licensing/public-performance requirements that apply to where and how you use it.

---

# References

- Mixxx manual: https://manual.mixxx.org/
- Mixxx MIDI scripting: https://github.com/mixxxdj/mixxx/wiki/midi-scripting
- loopMIDI (Windows virtual MIDI): https://www.tobias-erichsen.de/software/loopmidi.html
- VB-Audio Cable (Windows virtual audio): https://vb-audio.com/Cable/
- libspotifyctl (Windows Spotify control): https://pypi.org/project/libspotifyctl/
- Apple IAC Driver: https://support.apple.com/guide/audio-midi-setup/transfer-midi-information-between-apps-ams1013/mac
- BlackHole (macOS virtual audio): https://github.com/ExistentialAudio/BlackHole
- MPRIS (Linux media player interface): https://specifications.freedesktop.org/mpris-spec/latest/

---

# License

MIT
