# Mixxx Spotify Proxy for macOS

A small, unofficial macOS bridge that makes a normal Mixxx deck behave like a **proxy deck for the official Spotify desktop app**.

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

```text
                            CONTROL

Mixxx Deck 1 / Deck 2
        |
        v
SpotifyMixxx.js
        |
        | MIDI
        v
macOS IAC bus "SpotifyMixxx"
        |
        v
spotify_bridge.py
        |
        | AppleScript
        v
official Spotify.app


                             AUDIO

official Spotify.app
        |
        v
BlackHole 2ch
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

---

# Requirements

You need:

- macOS
- Mixxx
- the official Spotify desktop application
- a Spotify account that can play music in the desktop app
- Python 3
- BlackHole 2ch virtual audio driver
- the built-in macOS IAC Driver
- `ffmpeg` once, to create the small sentinel MP3

A DJ controller is optional. This also works with only the Mixxx GUI.

## Tested versions

This setup has been tested successfully with:

- Mixxx 2.5.6 on an MacOS
- Mixxx 2.7 development build on Apple Silicon

### Important Intel / Mixxx 2.7 note

During testing, one Intel Mac running a Mixxx 2.7 alpha build had an unusual issue where MIDI output from Mixxx to an IAC virtual MIDI port dropped messages, although MIDI output to a physical controller worked correctly. The same scripts worked correctly in Mixxx 2.5.6 on that Intel Mac.

If PLAY works but PAUSE/CUE commands appear to be missing, and the Python bridge does not print the missing MIDI message, try Mixxx 2.5.6 before changing the scripts.

---

# Installation walkthrough

The instructions below assume you are not already familiar with virtual audio, virtual MIDI, or Python environments.

## 1. Install the official Spotify desktop app

Install Spotify for macOS and sign in.

Before doing anything else, verify that Spotify can normally play a song.

Keep the Spotify app installed under its normal application name:

```text
Spotify.app
```

The Python bridge controls that application locally using AppleScript.

---

## 2. Verify local Spotify control

Open **Terminal**.

Try:

```bash
osascript -e 'tell application "Spotify" to playpause'
```

Spotify should immediately toggle between play and pause.

Try:

```bash
osascript -e 'tell application "Spotify" to get player position'
```

You should get a number such as:

```text
26.846000671387
```

Finally try:

```bash
osascript -e 'tell application "Spotify" to set player position to 30'
```

Spotify should jump to approximately 30 seconds into the current song.

If these commands do not work, stop here. The bridge depends on the local Spotify AppleScript interface.

---

## 3. Install BlackHole 2ch

BlackHole is a virtual macOS audio device. It lets Spotify send audio into Mixxx without a physical cable.

If you use Homebrew:

```bash
brew install blackhole-2ch
```

Alternatively, install the BlackHole 2ch package from the BlackHole project.

After installation, restart your Mac if the installer asks you to.

Open:

```text
Applications
  -> Utilities
     -> Audio MIDI Setup
```

Make sure **BlackHole 2ch** appears as an audio device.

Official project:

https://github.com/ExistentialAudio/BlackHole

---

## 4. Route Spotify/system audio into BlackHole

Spotify for macOS normally follows the macOS system audio output.

The simplest setup for a DJ laptop with a separate Mixxx audio interface is:

```text
macOS system output -> BlackHole 2ch
Mixxx Master        -> your real DJ audio interface
Mixxx Headphones    -> your real DJ audio interface
```

This means Spotify goes into BlackHole while Mixxx still sends its master/headphone output directly to your DJ interface.

Open macOS **Sound** settings and select:

```text
BlackHole 2ch
```

as the system output device.

### Important

When BlackHole is the system output you will not hear Spotify directly through the Mac speakers. That is expected.

You will hear Spotify after BlackHole has been configured as **Mixxx AUX1** and AUX1 is enabled.

Also remember that other normal macOS system sounds can enter BlackHole. For a DJ laptop it is a good idea to disable notification sounds / Do Not Disturb while performing.

---

## 5. Configure BlackHole as Mixxx AUX1

Open Mixxx.

Go to:

```text
Preferences
  -> Sound Hardware
```

In the input configuration, configure:

```text
Auxiliary 1 -> BlackHole 2ch -> Channels 1-2
```

Your normal Mixxx master/headphone outputs should remain assigned to your real audio interface.

Apply the changes.

### Quick test

Temporarily enable/play AUX1 in Mixxx.

Start Spotify.

You should see/hear Spotify arriving on AUX1.

If AUX1 receives no audio, do not continue to the MIDI/Python setup yet. Fix the audio routing first.

---

# Virtual MIDI setup

## 6. Create an IAC MIDI bus called `SpotifyMixxx`

IAC Driver is built into macOS. You do **not** need to download a MIDI driver.

Open:

```text
Applications
  -> Utilities
     -> Audio MIDI Setup
```

Then choose:

```text
Window
  -> Show MIDI Studio
```

Double-click:

```text
IAC Driver
```

Make sure:

```text
Device is online
```

is enabled.

Under **Ports**, click the `+` button to create a new bus.

Rename it exactly:

```text
SpotifyMixxx
```

Capitalization is not important to the Python bridge, but using exactly this name makes the setup easier to understand.

Close Audio MIDI Setup.

Apple's IAC documentation:

https://support.apple.com/guide/audio-midi-setup/transfer-midi-information-between-apps-ams1013/mac

---

# Python bridge

## 7. Install Python 3 if necessary

Check whether Python 3 already exists:

```bash
python3 --version
```

If you get something like:

```text
Python 3.12.4
```

you are ready.

If `python3` is not found, install Python 3. A common option if you already use Homebrew is:

```bash
brew install python
```

---

## 8. Open the project directory

In Terminal, change into the directory where you downloaded/cloned this repository.

For example:

```bash
cd ~/Downloads/mixxx-spotify-proxy
```

Use your real path if it is somewhere else.

Check that you can see:

```bash
ls
```

You should have at least:

```text
README.md
SpotifyMixxx.js
SpotifyMixxx.midi.xml
spotify_bridge.py
requirements.txt
```

---

## 9. Create a Python virtual environment

This keeps the one Python dependency for this project isolated from the rest of your Mac.

From the project directory run:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Your shell prompt will normally show `(.venv)` at the beginning.

Install the dependency:

```bash
python -m pip install -r requirements.txt
```

This installs:

```text
python-rtmidi
```

---

## 10. Test the Python bridge manually

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
```

Then:

```bash
python spotify_bridge.py pause
```

Then:

```bash
python spotify_bridge.py cue
```

`cue` should pause Spotify and move the current track back to the beginning.

Try volume:

```bash
python spotify_bridge.py volume 50
```

If these work, the Python -> Spotify part is ready.

---

## 11. Run the bridge in MIDI listener mode

Simply run:

```bash
python spotify_bridge.py
```

You should see:

```text
[SpotifyMixxx] Listening on MIDI input: "IAC Driver SpotifyMixxx"
[SpotifyMixxx] Ctrl-C to stop.
```

Leave this Terminal window running while you use the Spotify proxy.

When Mixxx later sends commands you will see messages such as:

```text
[SpotifyMixxx] MIDI: PLAY
[SpotifyMixxx] MIDI: PAUSE
[SpotifyMixxx] MIDI: CUE
[SpotifyMixxx] MIDI: VOLUME cc=127 -> 100
```

To stop the bridge, press:

```text
Control-C
```

### Starting it again later

Each time you open a new Terminal window:

```bash
cd ~/path/to/mixxx-spotify-proxy
source .venv/bin/activate
python spotify_bridge.py
```

---

# Install the Mixxx integration

## 12. Find the Mixxx user controller/mapping directory

The easiest and safest method is from Mixxx itself.

Open:

```text
Preferences
  -> Controllers
```

Click the button that opens the **User Mapping / User Preset Folder**.

Do not modify Mixxx's built-in controller files inside the application bundle.

Copy these two files from this repository into the Mixxx user controller folder:

```text
SpotifyMixxx.js
SpotifyMixxx.midi.xml
```

Restart Mixxx after copying them.

---

## 13. Enable the `SpotifyMixxx` virtual controller

Open:

```text
Mixxx
  -> Preferences
     -> Controllers
```

You should see an IAC device named approximately:

```text
IAC Driver SpotifyMixxx
```

Select it.

Load/select the mapping:

```text
SpotifyMixxx
```

Make sure the controller/mapping is enabled.

This mapping intentionally contains no normal MIDI button mappings. Its purpose is to make Mixxx load `SpotifyMixxx.js` and give that JavaScript file access to the IAC MIDI output.

Your existing physical DJ controller mapping remains unchanged.

---

# Create the sentinel track

## 14. Install ffmpeg if necessary

Check:

```bash
ffmpeg -version
```

If it is not installed and you use Homebrew:

```bash
brew install ffmpeg
```

---

## 15. Create `spotify-silence.mp3`

Run:

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

Why not absolute silence?

Mixxx may spend longer analyzing completely silent files. The `-90 dB` tone is effectively inaudible for this purpose but gives Mixxx immediate audio data to analyze.

The script identifies the sentinel by:

```text
approximately 10 seconds
44100 Hz sample rate
```

It does **not** depend on a particular filesystem path.

---

## 16. Import the sentinel into Mixxx

Move `spotify-silence.mp3` somewhere permanent in your music library.

Do not later delete or rename it unless you also update your Mixxx library.

Import it into Mixxx.

For convenience, create a crate such as:

```text
Spotify
```

and put only:

```text
spotify-silence.mp3
```

inside that crate.

This makes it very fast to load the proxy track during a party.

---

# First end-to-end test

## 17. Prepare everything

Before testing, verify:

1. Spotify desktop app is running.
2. A Spotify song is selected.
3. macOS system audio is routed to BlackHole 2ch.
4. Mixxx AUX1 input is BlackHole 2ch.
5. IAC `SpotifyMixxx` is enabled in Mixxx.
6. The `SpotifyMixxx` mapping is loaded.
7. The Python bridge is running:

```bash
python spotify_bridge.py
```

---

## 18. Load the proxy into Deck 1

In Mixxx, load:

```text
spotify-silence.mp3
```

into Deck 1.

Within about 250 ms, `SpotifyMixxx.js` recognizes the sentinel.

It then automatically:

- disables AutoDJ
- enables AUX1
- enables repeat on the short sentinel
- routes AUX1 to the left side of the crossfader
- mirrors the deck fader to AUX1
- mirrors PFL to AUX1
- mirrors FX assignments to AUX1

The script intentionally does **not** automatically re-enable AutoDJ later.

---

## 19. Press PLAY

Press PLAY on Deck 1.

This can be:

- the Mixxx GUI
- a keyboard mapping
- your normal physical controller

The Python terminal should print:

```text
[SpotifyMixxx] MIDI: PLAY
```

and Spotify should begin playing.

Press PLAY again to pause.

You should see:

```text
[SpotifyMixxx] MIDI: PAUSE
```

---

## 20. Test CUE

Press the normal Deck 1 CUE control.

The bridge should print:

```text
[SpotifyMixxx] MIDI: CUE
```

Spotify should pause and return to the beginning of the selected Spotify track.

---

## 21. Test PFL

Turn on PFL for the proxy deck.

The script mirrors that to:

```text
AUX1 PFL
```

so the Spotify audio can be previewed through the normal Mixxx headphone path.

---

## 22. Test the channel fader

Move the proxy deck's channel fader.

The script mirrors that value to:

```text
AUX1 volume
```

The audible Spotify signal should follow the normal deck fader.

---

## 23. Test the crossfader

If `spotify-silence.mp3` is loaded in Deck 1:

```text
AUX1 -> LEFT side of crossfader
```

If it is loaded in Deck 2:

```text
AUX1 -> RIGHT side of crossfader
```

So Spotify should behave as if its audio were physically coming from that deck.

---

## 24. Test FX

Assign an FX unit to the Spotify proxy deck.

The script also enables that same FX unit for AUX1.

It does not clone the effect. The same Mixxx FX unit is simply routed to both the silent proxy deck and AUX1, so the actual Spotify audio is processed by the effect.

---

# Normal party workflow

Once everything is configured, the practical workflow is short:

1. Someone requests a song you do not have locally.
2. Search for it in the normal Spotify app.
3. Select the requested Spotify song.
4. In Mixxx, open the `Spotify` crate.
5. Load `spotify-silence.mp3` into whichever deck is free.
6. Use PFL normally.
7. Press PLAY normally.
8. Transition with the channel fader / FX / crossfader normally.
9. While Spotify is playing, prepare the next normal local Mixxx track.
10. Load a normal track over `spotify-silence.mp3` when you are finished.

When the sentinel disappears from the proxy deck:

- repeat is turned off
- Spotify is paused
- AUX1 PFL is cleared
- AUX1 FX routing is cleared
- AUX1 crossfader orientation returns to center
- AUX1 is disabled
- the Mixxx deck returns to completely normal operation

---

# If you accidentally load the sentinel into both decks

Only one Spotify source exists, so only one deck may control it.

The script protects against accidentally loading `spotify-silence.mp3` in both Deck 1 and Deck 2:

- if one proxy deck is already active, it keeps ownership
- the second sentinel is ignored
- when the active sentinel is removed, the remaining sentinel can become the proxy
- if both were already loaded when the script starts, Deck 1 wins

---

# Troubleshooting

## Python says it cannot find `SpotifyMixxx`

Example:

```text
Could not find MIDI input containing "SpotifyMixxx"
```

Check:

```text
Audio MIDI Setup
 -> MIDI Studio
 -> IAC Driver
```

Make sure:

- Device is online
- a port exists
- it is named `SpotifyMixxx`

Restart the Python bridge after creating/renaming the IAC port.

---

## Mixxx does not show the IAC device

Quit and restart Mixxx after creating the IAC port.

Then check:

```text
Preferences -> Controllers
```

---

## Python works manually but receives nothing from Mixxx

First verify the script is loaded.

Look in the Mixxx log for:

```text
[SpotifyMixxx] initializing
[SpotifyMixxx] ready
```

Then load the sentinel. You should see a log entry showing that the proxy mode was activated.

If the script is not loading:

- confirm both files are in the Mixxx user controller folder
- confirm `SpotifyMixxx.midi.xml` references `SpotifyMixxx.js`
- confirm the IAC device has the `SpotifyMixxx` mapping selected and enabled

---

## PLAY arrives but PAUSE/CUE messages are missing on Intel Mac

This was observed with one **Mixxx 2.7 build**.

If you see that exact pattern, try Mixxx 2.5.6 rather than changing the bridge code.

---

## Spotify is playing but you cannot hear it

Check the audio path in order:

```text
Spotify
 -> macOS system output
 -> BlackHole 2ch
 -> Mixxx Auxiliary 1
 -> Mixxx master
```

Temporarily enable AUX1 manually in Mixxx and check whether its meter moves.

---

## I can hear Spotify regardless of the crossfader

The script expects AUX1 to participate in Mixxx's main mix using:

```text
[Auxiliary1],main_mix
```

and sets:

```text
orientation = 0  for Deck 1
orientation = 2  for Deck 2
```

Make sure you are using the supplied `SpotifyMixxx.js` rather than an older version that used the wrong AUX routing control.

---

## The sentinel takes a long time to load

Use the supplied 10-second / -90 dB sentinel recipe.

Do not use a 30-minute file or a huge file containing absolute digital silence.

---

## Spotify volume stops at unity gain

This is intentional.

The deck gain is mapped to Spotify's own application volume, which only has a finite 0-100 range.

Mixxx deck pregain values above unity are therefore clamped to Spotify volume 100.

The actual channel fader remains handled inside Mixxx through AUX1.

---

# Files in this repository

```text
SpotifyMixxx.js
```

Mixxx-side logic. Detects the sentinel, watches Deck 1/2, mirrors Mixxx routing to AUX1 and sends transport/volume commands over MIDI.

```text
SpotifyMixxx.midi.xml
```

Small virtual-controller mapping whose main purpose is to load `SpotifyMixxx.js` for the IAC device.

```text
spotify_bridge.py
```

Listens to the `SpotifyMixxx` IAC MIDI port and translates commands to local Spotify AppleScript commands.

```text
requirements.txt
```

Contains the Python dependency (`python-rtmidi`).

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

This is not native Spotify support in Mixxx.

You do not get:

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
- calls the local macOS `osascript` command
- does not require Spotify API credentials
- does not require OAuth
- does not contain a Spotify password
- does not contact a custom server

Spotify authentication remains entirely inside the official Spotify application.

---

# Legal / service terms

This is an unofficial community project and is not affiliated with Spotify, Mixxx, Apple, or the BlackHole project.

It does not bypass Spotify DRM or create downloadable copies of Spotify tracks.

You are responsible for complying with Spotify's terms and any music licensing/public-performance requirements that apply to where and how you use it.

---

# References

- Mixxx manual: https://manual.mixxx.org/
- Mixxx MIDI scripting: https://github.com/mixxxdj/mixxx/wiki/midi-scripting
- Apple IAC Driver: https://support.apple.com/guide/audio-midi-setup/transfer-midi-information-between-apps-ams1013/mac
- BlackHole: https://github.com/ExistentialAudio/BlackHole

---

# License

MIT
