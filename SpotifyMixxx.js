/*
 * SpotifyMixxx.js
 *
 * Mixxx-side Spotify proxy integration.
 *
 * A special silent track acts as a sentinel. When that track is loaded into
 * Deck 1 or Deck 2, that deck becomes a proxy control surface for Spotify.
 *
 * Mixxx-side actions are handled directly here:
 *   Deck PFL            -> AUX1 PFL
 *   Deck channel fader -> AUX1 volume
 *   Deck FX routing     -> same FX unit routed to AUX1
 *   Deck 1 proxy        -> AUX1 crossfader LEFT
 *   Deck 2 proxy        -> AUX1 crossfader RIGHT
 *
 * Spotify transport/gain commands are sent as MIDI to spotify_bridge.py:
 *   Deck play=1 -> PLAY
 *   Deck play=0 -> PAUSE
 *   CUE press   -> CUE
 *   Deck pregain -> Spotify sound volume
 *
 * IMPORTANT: Mixxx does not expose the loaded filename as a normal deck
 * ControlObject. Therefore V1 identifies spotify-silence.mp3 by fingerprint:
 *
 *     10 seconds at 44100 Hz
 *
 * Create the sentinel with e.g.:
 *
 *   ffmpeg -f lavfi \
 *     -i "sine=frequency=1000:sample_rate=44100:duration=10" \
 *     -af "volume=-90dB" \
 *     -q:a 9 -acodec libmp3lame spotify-silence.mp3
 *
 * MP3 encoder padding may make the decoded duration differ slightly, so a
 * +/- 1 second tolerance is used.
 */

var SpotifyMixxx = {};

SpotifyMixxx.AUX = "[Auxiliary1]";
SpotifyMixxx.DECKS = ["[Channel1]", "[Channel2]"];

SpotifyMixxx.SENTINEL_DURATION = 10.0;
SpotifyMixxx.SENTINEL_DURATION_TOLERANCE = 1.0;
SpotifyMixxx.SENTINEL_SAMPLE_RATE = 44100;

SpotifyMixxx.FX_UNITS = 4;

// MIDI protocol to spotify_bridge.py
SpotifyMixxx.NOTE_PLAY = 0x10;
SpotifyMixxx.NOTE_PAUSE = 0x11;
SpotifyMixxx.NOTE_CUE = 0x12;
SpotifyMixxx.CC_VOLUME = 0x20;

SpotifyMixxx.connections = [];
SpotifyMixxx.spotifyMode = {
    "[Channel1]": false,
    "[Channel2]": false
};
SpotifyMixxx.activeDeck = null;
SpotifyMixxx.identityTimer = 0;
SpotifyMixxx.lastFingerprint = {
    "[Channel1]": "",
    "[Channel2]": ""
};


SpotifyMixxx.log = function(message) {
    console.log("[SpotifyMixxx] " + message);
};


SpotifyMixxx.sendNote = function(note) {
    SpotifyMixxx.log("MIDI OUT note=" + note);
    midi.sendShortMsg(0x90, note, 0x7F);
};


SpotifyMixxx.sendVolume = function(pregain) {
    /*
     * Mixxx pregain is 0..1..4, where 1 is unity.
     * Spotify only has 0..100 volume and cannot amplify above 100.
     *
     * Therefore:
     *   pregain 0.0 -> Spotify 0
     *   pregain 1.0 -> Spotify 100
     *   pregain >1  -> Spotify stays at 100
     */
    var normalized = Math.max(0.0, Math.min(1.0, pregain));
    var midiValue = Math.round(normalized * 127.0);
    midi.sendShortMsg(0xB0, SpotifyMixxx.CC_VOLUME, midiValue);
};


SpotifyMixxx.isSentinelLoaded = function(group) {
    var loaded = engine.getValue(group, "track_loaded");
    var trackSamples = engine.getValue(group, "track_samples");
    var sampleRate = engine.getValue(group, "track_samplerate");

    var duration = 0;
    if (sampleRate > 0) {
        // Engine sample count is stereo/interleaved in Mixxx.
        duration = trackSamples / (sampleRate * 2.0);
    }

    var fingerprint =
        "loaded=" + loaded +
        " samples=" + trackSamples +
        " samplerate=" + sampleRate +
        " duration=" + duration.toFixed(3);

    if (fingerprint !== SpotifyMixxx.lastFingerprint[group]) {
        SpotifyMixxx.lastFingerprint[group] = fingerprint;
        SpotifyMixxx.log(group + " identity: " + fingerprint);
    }

    if (loaded === 0) {
        return false;
    }

    var durationMatches =
        Math.abs(duration - SpotifyMixxx.SENTINEL_DURATION) <=
        SpotifyMixxx.SENTINEL_DURATION_TOLERANCE;

    return durationMatches && sampleRate === SpotifyMixxx.SENTINEL_SAMPLE_RATE;
};

SpotifyMixxx.fxDeckKey = function(group) {
    return "group_" + group + "_enable";
};


SpotifyMixxx.fxAuxKey = function() {
    return "group_" + SpotifyMixxx.AUX + "_enable";
};


SpotifyMixxx.mirrorFxUnit = function(group, unitNumber) {
    if (!SpotifyMixxx.spotifyMode[group] || SpotifyMixxx.activeDeck !== group) {
        return;
    }

    var fxGroup = "[EffectRack1_EffectUnit" + unitNumber + "]";
    var enabled = engine.getValue(fxGroup, SpotifyMixxx.fxDeckKey(group));
    engine.setValue(fxGroup, SpotifyMixxx.fxAuxKey(), enabled);
};


SpotifyMixxx.clearAuxFx = function() {
    for (var i = 1; i <= SpotifyMixxx.FX_UNITS; ++i) {
        var fxGroup = "[EffectRack1_EffectUnit" + i + "]";
        engine.setValue(fxGroup, SpotifyMixxx.fxAuxKey(), 0);
    }
};


SpotifyMixxx.syncDeckToAux = function(group) {
    if (SpotifyMixxx.activeDeck !== group) {
        return;
    }

    engine.setValue(SpotifyMixxx.AUX, "main_mix", 1);
    engine.setValue(SpotifyMixxx.AUX, "pfl", engine.getValue(group, "pfl"));
    engine.setValue(SpotifyMixxx.AUX, "volume", engine.getValue(group, "volume"));

    // Fixed crossfader assignment requested by design:
    // Deck 1 -> left (0), Deck 2 -> right (2)
    var auxOrientation = group === "[Channel1]" ? 0 : 2;
    engine.setValue(SpotifyMixxx.AUX, "orientation", auxOrientation);
    SpotifyMixxx.log(
        "AUX1 main_mix=" + engine.getValue(SpotifyMixxx.AUX, "main_mix") +
        " orientation=" + engine.getValue(SpotifyMixxx.AUX, "orientation")
    );

    for (var i = 1; i <= SpotifyMixxx.FX_UNITS; ++i) {
        SpotifyMixxx.mirrorFxUnit(group, i);
    }

    // Make Spotify state explicitly match Mixxx state.
    if (engine.getValue(group, "play") > 0) {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_PLAY);
    } else {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_PAUSE);
    }

    SpotifyMixxx.sendVolume(engine.getValue(group, "pregain"));
};


SpotifyMixxx.activateDeck = function(group) {
    if (SpotifyMixxx.activeDeck === group && SpotifyMixxx.spotifyMode[group]) {
        return;
    }

    // A single Spotify.app/AUX1 source can only represent one proxy deck.
    if (SpotifyMixxx.activeDeck !== null && SpotifyMixxx.activeDeck !== group) {
        SpotifyMixxx.log(
            "Spotify proxy moved from " + SpotifyMixxx.activeDeck + " to " + group
        );
        SpotifyMixxx.spotifyMode[SpotifyMixxx.activeDeck] = false;
    }

    SpotifyMixxx.spotifyMode[group] = true;
    SpotifyMixxx.activeDeck = group;

    // Safety precaution: Spotify proxy mode must never coexist with AutoDJ.
    // We intentionally do NOT restore AutoDJ when Spotify mode ends.
    engine.setValue("[AutoDJ]", "enabled", 0);

    // Make sure AUX1 is actually running.
    engine.setValue(SpotifyMixxx.AUX, "enabled", 1);

    // Keep the short sentinel running indefinitely while Spotify is active.
    engine.setValue(group, "repeat", 1);

    SpotifyMixxx.log(
        group + " entered Spotify proxy mode; AutoDJ disabled; AUX1 enabled; repeat enabled"
    );
    SpotifyMixxx.syncDeckToAux(group);
};


SpotifyMixxx.deactivateDeck = function(group) {
    if (!SpotifyMixxx.spotifyMode[group]) {
        return;
    }

    SpotifyMixxx.spotifyMode[group] = false;

    // Restore normal deck behavior when the sentinel is no longer loaded.
    engine.setValue(group, "repeat", 0);

    // Stop/disable AUX1 when leaving Spotify proxy mode.
    engine.setValue(SpotifyMixxx.AUX, "enabled", 0);

    if (SpotifyMixxx.activeDeck === group) {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_PAUSE);

        engine.setValue(SpotifyMixxx.AUX, "pfl", 0);
        engine.setValue(SpotifyMixxx.AUX, "orientation", 1); // center/default
        SpotifyMixxx.clearAuxFx();

        SpotifyMixxx.activeDeck = null;
        SpotifyMixxx.log(group + " left Spotify proxy mode");
    }
};


SpotifyMixxx.updateSentinelState = function(group) {
    if (SpotifyMixxx.isSentinelLoaded(group)) {
        SpotifyMixxx.activateDeck(group);
    } else {
        SpotifyMixxx.deactivateDeck(group);
    }
};


SpotifyMixxx.onTrackIdentityChanged = function(value, group, control) {
    // sample-count/sample-rate can update shortly after track_loaded, so all three
    // controls call the same check.
    SpotifyMixxx.updateSentinelState(group);
};


SpotifyMixxx.onPlayChanged = function(value, group, control) {
    SpotifyMixxx.log(
        "play changed " + group +
        " value=" + value +
        " spotifyMode=" + SpotifyMixxx.spotifyMode[group] +
        " activeDeck=" + SpotifyMixxx.activeDeck
    );

    if (!SpotifyMixxx.spotifyMode[group] || SpotifyMixxx.activeDeck !== group) {
        return;
    }

    if (value > 0) {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_PLAY);
    } else {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_PAUSE);
    }
};


SpotifyMixxx.onCueChanged = function(value, group, control) {
    if (!SpotifyMixxx.spotifyMode[group] || SpotifyMixxx.activeDeck !== group) {
        return;
    }

    // Act only on button press, not release.
    if (value > 0) {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_CUE);
    }
};


SpotifyMixxx.onPflChanged = function(value, group, control) {
    if (!SpotifyMixxx.spotifyMode[group] || SpotifyMixxx.activeDeck !== group) {
        return;
    }

    engine.setValue(SpotifyMixxx.AUX, "pfl", value > 0 ? 1 : 0);
};


SpotifyMixxx.onVolumeChanged = function(value, group, control) {
    if (!SpotifyMixxx.spotifyMode[group] || SpotifyMixxx.activeDeck !== group) {
        return;
    }

    engine.setValue(SpotifyMixxx.AUX, "volume", value);
};


SpotifyMixxx.onPregainChanged = function(value, group, control) {
    if (!SpotifyMixxx.spotifyMode[group] || SpotifyMixxx.activeDeck !== group) {
        return;
    }

    SpotifyMixxx.sendVolume(value);
};


SpotifyMixxx.onFxChanged = function(value, group, control) {
    if (SpotifyMixxx.activeDeck === null) {
        return;
    }

    // Here "group" is [EffectRack1_EffectUnitN].
    // Determine the unit number from its name.
    var match = group.match(/EffectUnit(\d+)\]/);
    if (!match) {
        return;
    }

    var unitNumber = parseInt(match[1], 10);
    SpotifyMixxx.mirrorFxUnit(SpotifyMixxx.activeDeck, unitNumber);
};


SpotifyMixxx.connect = function(group, control, callback) {
    var connection = engine.makeConnection(group, control, callback);
    SpotifyMixxx.connections.push(connection);
};


SpotifyMixxx.pollTrackIdentity = function() {
    var sentinelDecks = [];

    SpotifyMixxx.DECKS.forEach(function(group) {
        if (SpotifyMixxx.isSentinelLoaded(group)) {
            sentinelDecks.push(group);
        }
    });

    if (sentinelDecks.length === 0) {
        SpotifyMixxx.DECKS.forEach(function(group) {
            SpotifyMixxx.deactivateDeck(group);
        });
        return;
    }

    if (sentinelDecks.length === 1) {
        var owner = sentinelDecks[0];

        SpotifyMixxx.DECKS.forEach(function(group) {
            if (group === owner) {
                SpotifyMixxx.activateDeck(group);
            } else {
                SpotifyMixxx.deactivateDeck(group);
            }
        });
        return;
    }

    if (
        SpotifyMixxx.activeDeck !== null &&
        sentinelDecks.indexOf(SpotifyMixxx.activeDeck) !== -1
    ) {
        SpotifyMixxx.log(
            "Both decks contain Spotify sentinel; keeping " +
            SpotifyMixxx.activeDeck + " as active proxy"
        );

        SpotifyMixxx.DECKS.forEach(function(group) {
            if (group !== SpotifyMixxx.activeDeck) {
                SpotifyMixxx.spotifyMode[group] = false;
            }
        });

        return;
    }

    SpotifyMixxx.log(
        "Both decks contain Spotify sentinel and no proxy is active; " +
        "defaulting to [Channel1]"
    );
    SpotifyMixxx.activateDeck("[Channel1]");
    SpotifyMixxx.spotifyMode["[Channel2]"] = false;
};


SpotifyMixxx.init = function(id, debug) {
    SpotifyMixxx.log("initializing");

    SpotifyMixxx.DECKS.forEach(function(group) {
        SpotifyMixxx.connect(group, "play", SpotifyMixxx.onPlayChanged);
        SpotifyMixxx.connect(group, "cue_default", SpotifyMixxx.onCueChanged);
        SpotifyMixxx.connect(group, "pfl", SpotifyMixxx.onPflChanged);
        SpotifyMixxx.connect(group, "volume", SpotifyMixxx.onVolumeChanged);
        SpotifyMixxx.connect(group, "pregain", SpotifyMixxx.onPregainChanged);

        for (var i = 1; i <= SpotifyMixxx.FX_UNITS; ++i) {
            var fxGroup = "[EffectRack1_EffectUnit" + i + "]";
            SpotifyMixxx.connect(
                fxGroup,
                SpotifyMixxx.fxDeckKey(group),
                SpotifyMixxx.onFxChanged
            );
        }
    });

    // Poll read-only track identity values. This is intentionally timer-based:
    // some read-only metadata controls are not reliable output signals for
    // controller callbacks, but engine.getValue() can always inspect them.
    SpotifyMixxx.identityTimer = engine.beginTimer(
        250,
        SpotifyMixxx.pollTrackIdentity
    );

    // Initial check immediately, without waiting for the first timer tick.
    SpotifyMixxx.pollTrackIdentity();

    SpotifyMixxx.log(
        "ready; identity poll timer=" + SpotifyMixxx.identityTimer
    );
};


SpotifyMixxx.shutdown = function() {
    SpotifyMixxx.log("shutting down");

    if (SpotifyMixxx.identityTimer) {
        engine.stopTimer(SpotifyMixxx.identityTimer);
        SpotifyMixxx.identityTimer = 0;
    }

    if (SpotifyMixxx.activeDeck !== null) {
        SpotifyMixxx.sendNote(SpotifyMixxx.NOTE_PAUSE);
    }

    engine.setValue(SpotifyMixxx.AUX, "pfl", 0);
    engine.setValue(SpotifyMixxx.AUX, "orientation", 1);
    SpotifyMixxx.clearAuxFx();

    SpotifyMixxx.connections.forEach(function(connection) {
        connection.disconnect();
    });
    SpotifyMixxx.connections = [];
    SpotifyMixxx.activeDeck = null;
};
