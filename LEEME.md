# Mixxx Spotify Proxy (multiplataforma) — Instrucciones en español

Un puente no oficial y pequeño que hace que un deck normal de Mixxx se comporte como un **deck proxy para la aplicación de escritorio oficial de Spotify**.

Plataformas compatibles:

- **Windows** (mediante `libspotifyctl`, SMTC + Core Audio)
- **macOS** (mediante AppleScript)
- **Linux** (mediante D-Bus MPRIS)

Está pensado para la situación ocasional en la que estás pinchando (DJ) con archivos locales en Mixxx y alguien pide una canción que solo tienes en Spotify.

Este proyecto **no descarga, descifra, extrae ni expone archivos de audio de Spotify**. Spotify sigue reproduciendo el audio en la aplicación oficial. Mixxx recibe ese audio a través de una entrada de audio virtual y refleja los controles normales del deck hacia él.

---

## Qué se siente cuando funciona

Encuentras una canción manualmente en Spotify y luego cargas un archivo especial de 10 segundos llamado `spotify-silence.mp3` en el deck libre de Mixxx.

A partir de ahí:

| Control de Mixxx | Qué pasa |
|---|---|
| PLAY | Spotify reproduce |
| Pausa / PLAY desactivado | Spotify pausa |
| CUE | Spotify pausa y salta al inicio |
| Ganancia del deck | Cambia el volumen de la app de Spotify |
| Fader de canal | El volumen de AUX1 de Mixxx sigue al deck |
| PFL | El PFL de AUX1 sigue al deck |
| Asignación de FX | La misma unidad de FX de Mixxx se enruta a AUX1 |
| Crossfader, Spotify en Deck 1 | AUX1 se asigna al lado izquierdo |
| Crossfader, Spotify en Deck 2 | AUX1 se asigna al lado derecho |

El comando puede venir de la GUI de Mixxx, de un atajo de teclado o de tu controlador DJ normal. El script de Spotify observa los controles internos de Deck 1 / Deck 2 de Mixxx, así que no necesita modificar el mapeo de tu controlador físico.

Cuando se quita la pista centinela, el proxy de Spotify se apaga y AUX1 se desactiva.

---

# Arquitectura

```
                            CONTROL

Mixxx Deck 1 / Deck 2
        |
        v
SpotifyMixxx.js
        |
        | MIDI (puerto virtual "SpotifyMixxx")
        v
spotify_bridge.py
        |
        | Backend según el SO
        |   macOS:   AppleScript
        |   Windows: libspotifyctl (SMTC / Core Audio)
        |   Linux:   D-Bus MPRIS
        v
aplicación oficial de Spotify


                             AUDIO

aplicación oficial de Spotify
        |
        v
dispositivo de audio virtual (mac: BlackHole / win: VB-Cable /
                        linux: monitor de PulseAudio/PipeWire)
        |
        v
Mixxx AUX1
        |
        v
PFL / FX / fader de canal / crossfader
        |
        v
Mixxx Master (salida maestra)
```

La lógica del lado de Mixxx (`SpotifyMixxx.js`) y el mapeo MIDI XML son **idénticos en las tres plataformas**. Solo cambian el backend de control de Spotify y el cableado de MIDI/audio virtual.

---

# Requisitos

Necesitas:

- Una de estas: Windows 10/11, macOS o Linux
- Mixxx
- la aplicación de escritorio oficial de Spotify
- una cuenta de Spotify que pueda reproducir música en la app de escritorio
- Python 3
- Un puerto MIDI virtual llamado `SpotifyMixxx` (herramienta según la plataforma, ver abajo)
- Una entrada de audio virtual (herramienta según la plataforma, ver abajo)
- `ffmpeg` una vez, para crear el MP3 centinela pequeño

Un controlador DJ es opcional. Esto también funciona solo con la GUI de Mixxx.

---

# Componentes según la plataforma

Usa solo las secciones relevantes para tu sistema operativo.

## Windows

| Componente | Herramienta | Notas |
|---|---|---|
| Control de Spotify | `libspotifyctl` | offline, sin OAuth — `pip install libspotifyctl` |
| MIDI virtual | [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) | gratis |
| Audio virtual | [VB-Audio Cable](https://vb-audio.com/Cable/) | gratis (donation-ware) |

### Windows: MIDI virtual (loopMIDI)

1. Descarga y ejecuta loopMIDI desde https://www.tobias-erichsen.de/software/loopmidi.html
2. Pulsa el botón `+` en la parte inferior izquierda para añadir un puerto.
3. Ponle como nombre `SpotifyMixxx` (exactamente).
4. Mantén loopMIDI en ejecución (se minimiza a la bandeja del sistema).
5. Reinicia Mixxx para que detecte el nuevo puerto.

### Windows: audio virtual (VB-Audio Cable)

1. Descarga e instala VB-Audio Cable desde https://vb-audio.com/Cable/ (ejecuta el instalador como Administrador, reinicia si lo pide).
2. En **Configuración de Windows → Sistema → Sonido → Mezclador de volumen**, cambia el dispositivo de salida **solo para Spotify** a `CABLE Input (VB-Cable)`.
3. En Mixxx, en **Preferencias → Hardware de sonido → Entrada**, configura:
   ```
   Auxiliar 1 -> CABLE Output (VB-Cable) -> Canales 1-2
   ```
   Deja tus salidas de master/auriculares de Mixxx en tu interfaz de audio real.
4. Aplica y verifica que el audio de Spotify llega a AUX1 antes de continuar.

> En la configuración de sonido de Windows el dispositivo puede aparecer como "CABLE Input / CABLE Output".

---

## macOS

| Componente | Herramienta | Notas |
|---|---|---|
| Control de Spotify | AppleScript | incluido |
| MIDI virtual | IAC Driver | incluido |
| Audio virtual | [BlackHole](https://github.com/ExistentialAudio/BlackHole) | gratis (Homebrew `brew install blackhole-2ch`) |

### macOS: MIDI virtual (bus IAC)

IAC Driver está integrado. En resumen:

1. Abre `Aplicaciones → Utilidades → Configuración Audio MIDI`
2. `Ventana → Mostrar estudio MIDI`
3. Haz doble clic en **IAC Driver**, activa **Dispositivo en línea**
4. En **Puertos**, pulsa `+`, renombra el bus a `SpotifyMixxx`
5. Reinicia Mixxx.

### macOS: audio virtual (BlackHole)

1. `brew install blackhole-2ch` (o instala el paquete del proyecto BlackHole).
2. Establece **BlackHole 2ch** como salida del sistema en macOS (Spotify sigue la salida del sistema).
3. En Mixxx, en **Preferencias → Hardware de sonido → Entrada**, configura:
   ```
   Auxiliar 1 -> BlackHole 2ch -> Canales 1-2
   ```
4. No oirás Spotify por los altavoces hasta que AUX1 esté activado en Mixxx (esperado).

---

## Linux

| Componente | Herramienta | Notas |
|---|---|---|
| Control de Spotify | D-Bus MPRIS | integrado en la app de escritorio de Spotify |
| MIDI virtual | Puertos virtuales ALSA (`snd-virmidi`) | integrado en el kernel |
| Audio virtual | Monitor de PulseAudio / PipeWire / null-sink | integrado |

### Linux: MIDI virtual (ALSA)

El módulo del kernel `snd-virmidi` proporciona dispositivos MIDI raw virtuales:

```bash
sudo modprobe snd-virmidi
```

Esto crea puertos MIDI raw similares a `VirMIDI 1-0` / `Midi Through Port-0`, que Mixxx puede usar. Para crear un bucle (loopback) de modo que la salida de Mixxx llegue al puente Python, conecta los puertos con `aconnect`:

```bash
# Lista los puertos MIDI ALSA disponibles
aconnect -l
```

Mixxx escribe en una de las salidas `Midi Through Port-X`; el puente escucha en la entrada correspondiente. En sistemas con PipeWire, también puede estar disponible el bridging MIDI más nuevo (`pw-loopback`).

Una alternativa más sencilla que algunos prefieren es crear un puerto virtual usando el propio `rtmidi` del puente (ver más abajo), pero la vía documentada habitual son los puertos virtuales ALSA.

### Linux: audio virtual (null-sink de PulseAudio / PipeWire)

Crea un null sink al que Spotify emita y apunta Mixxx a su monitor:

```bash
# PulseAudio
pactl load-module module-null-sink sink_name=SpotifyMonitor sink_properties=device.description=SpotifyMonitor
```

```bash
# PipeWire (pipewire-pulse)
pactl load-module module-null-sink sink_name=SpotifyMonitor sink_properties=device.description=SpotifyMonitor
```

Enruta la salida de Spotify a `SpotifyMonitor` (p. ej. con `pavucontrol` → pestaña Reproducción → cambia el dispositivo de Spotify a *SpotifyMonitor*).

En Mixxx, en **Preferencias → Hardware de sonido → Entrada**, configura:

```
Auxiliar 1 -> SpotifyMonitor.monitor -> Canales 1-2
```

Si el sink no persiste tras reiniciar, añade la línea `load-module` a tu configuración de PulseAudio/PipeWire (p. ej. `~/.config/pulse/default.pa` para PulseAudio).

---

# El puente de Python

El script del puente es el mismo para todas las plataformas; detecta automáticamente el SO y carga el backend correcto.

## Instala Python 3 si es necesario

Comprueba:

```bash
python3 --version     # macOS / Linux
python --version      # Windows
```

Si obtienes algo como `Python 3.12.4`, ya estás listo.

## Abre el directorio del proyecto

```bash
cd ruta/al/mixxx-spotify-winli
```

Deberías tener al menos:

```text
README.md
SpotifyMixxx.js
SpotifyMixxx.midi.xml
spotify_bridge.py
spotify_backends/
requirements.txt
```

## Crea un entorno virtual de Python

```bash
python3 -m venv .venv
```

Actívalo:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat
```

Instala la dependencia base:

```bash
python -m pip install -r requirements.txt
```

Luego instala el backend de tu plataforma:

```bash
# Windows
python -m pip install libspotifyctl

# Linux
python -m pip install dbus-python
```

## Prueba el puente de Python manualmente

Con el entorno virtual activo:

```bash
python spotify_bridge.py status
```

Si Spotify tiene una pista seleccionada, deberías ver algo parecido a:

```text
Artista - Canción
26.8 / 201.4 seg
paused
```

Prueba:

```bash
python spotify_bridge.py play
python spotify_bridge.py pause
python spotify_bridge.py cue
python spotify_bridge.py volume 50
python spotify_bridge.py seek 30
```

`cue` pausa Spotify y mueve la pista actual al principio.

Si esto funciona, la parte Python → Spotify está lista.

## Ejecuta el puente en modo listener (escucha MIDI)

Simplemente ejecuta:

```bash
python spotify_bridge.py
```

Deberías ver algo como:

```text
[SpotifyMixxx] Spotify backend: windows   # o macos / linux
[SpotifyMixxx] Listening on MIDI input: "SpotifyMixxx"
[SpotifyMixxx] Ctrl-C to stop.
```

Deja esta ventana de terminal abierta mientras usas el proxy de Spotify.

Cuando Mixxx envíe comandos verás mensajes como:

```text
[SpotifyMixxx] MIDI: PLAY
[SpotifyMixxx] MIDI: PAUSE
[SpotifyMixxx] MIDI: CUE
[SpotifyMixxx] MIDI: VOLUME cc=127 -> 100
```

Para detener el puente, pulsa `Control-C`.

---

# Instala la integración en Mixxx

Lo siguiente es idéntico en todas las plataformas.

## Encuentra el directorio de usuario de controladores/mapeos de Mixxx

Abre:

```text
Preferencias -> Controladores
```

Pulsa el botón que abre la **Carpeta de mapeos/usuarios**. No modifiques los archivos de controladores integrados de Mixxx.

Copia estos dos archivos del repositorio a la carpeta de controladores de usuario de Mixxx:

```text
SpotifyMixxx.js
SpotifyMixxx.midi.xml
```

Reinicia Mixxx después de copiarlos.

## Activa el controlador virtual `SpotifyMixxx`

Abre `Mixxx → Preferencias → Controladores`. Deberías ver tu dispositivo MIDI virtual, p. ej.:

```text
Windows:  loopMIDI Port
macOS:    IAC Driver SpotifyMixxx
Linux:    Midi Through Port-X / VirMIDI ...
```

Selecciónalo y carga/selecciona el mapeo:

```text
SpotifyMixxx
```

Asegúrate de que el controlador/mapeo esté habilitado.

Este mapeo no contiene mapeos de botones MIDI normales a propósito. Su propósito es hacer que Mixxx cargue `SpotifyMixxx.js` y dar a ese archivo JavaScript acceso a la salida MIDI virtual. El mapeo de tu controlador físico existente no se modifica.

---

# Crea la pista centinela

## Instala ffmpeg si es necesario

```bash
ffmpeg -version
```

Si no está instalado:
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Windows: descarga una compilación o usa `winget install Gyan.FFmpeg`

## Crea `spotify-silence.mp3`

```bash
ffmpeg \
  -f lavfi \
  -i "sine=frequency=1000:sample_rate=44100:duration=10" \
  -af "volume=-90dB" \
  -q:a 9 \
  -acodec libmp3lame \
  spotify-silence.mp3
```

Esto crea un MP3 de 10 segundos a 44.1 kHz con un tono extremadamente silencioso.

¿Por qué no silencio absoluto? Mixxx puede tardar más en analizar archivos completamente silenciosos. El tono de `-90 dB` es prácticamente inaudible pero le da a Mixxx datos de audio al instante.

El script identifica la centinela por: aproximadamente 10 segundos y frecuencia de muestreo de 44100 Hz. No depende de una ruta de archivo concreta.

## Importa la centinela a Mixxx

Mueve `spotify-silence.mp3` a un lugar permanente de tu biblioteca de música, impórtalo en Mixxx y (recomendado) añádelo a una crate llamada `Spotify` para cargarlo rápido.

---

# Primera prueba de extremo a extremo

Antes de la prueba, verifica:

1. La app de escritorio de Spotify está en ejecución.
2. Hay una canción de Spotify seleccionada.
3. El audio de Spotify está enrutado a tu entrada de audio virtual (VB-Cable / BlackHole / monitor null-sink).
4. La entrada AUX1 de Mixxx es ese audio virtual.
5. El puerto MIDI virtual `SpotifyMixxx` está habilitado en Mixxx.
6. El mapeo `SpotifyMixxx` está cargado.
7. El puente de Python está en ejecución: `python spotify_bridge.py`

## Carga el proxy en el Deck 1

En Mixxx, carga `spotify-silence.mp3` en el Deck 1. En unos 250 ms, `SpotifyMixxx.js` reconoce la centinela y automáticamente:

- desactiva AutoDJ
- activa AUX1
- activa la repetición en la centinela corta
- enruta AUX1 al lado izquierdo del crossfader
- refleja el fader del deck en AUX1
- refleja el PFL en AUX1
- refleja las asignaciones de FX en AUX1

El script intencionadamente **no** reactiva AutoDJ automáticamente.

## Pulsa PLAY

Pulsa PLAY en el Deck 1 (GUI, mapeo de teclado o controlador DJ). La terminal de Python debería imprimir `[SpotifyMixxx] MIDI: PLAY` y Spotify debería empezar a reproducir. Pulsa PLAY otra vez para pausar (`MIDI: PAUSE`).

## Prueba CUE

Pulsa CUE en el Deck 1. El puente imprime `[SpotifyMixxx] MIDI: CUE`; Spotify pausa y vuelve al inicio.

## Prueba PFL

Activa el PFL del deck proxy. El script lo refleja en `AUX1 PFL`, así podrás previsualizar por la ruta de auriculares de Mixxx.

## Prueba el fader de canal

Mueve el fader de canal del deck proxy; se refleja en `volumen de AUX1`.

## Prueba el crossfader

- Centinela en Deck 1 → `AUX1 -> IZQUIERDA`
- Centinela en Deck 2 → `AUX1 -> DERECHA`

Spotify se comporta como si su audio viniera de ese deck.

## Prueba FX

Asigna una unidad de FX al deck proxy; el script enruta esa misma unidad de FX a AUX1, así el audio real de Spotify se procesa con el efecto.

---

# Flujo normal de una fiesta

1. Alguien pide una canción que no tienes localmente.
2. Búscala en la app normal de Spotify y selecciónala.
3. En Mixxx, abre la crate `Spotify`.
4. Carga `spotify-silence.mp3` en el deck que esté libre.
5. Usa PFL normalmente.
6. Pulsa PLAY normalmente.
7. Haz la transición con el fader de canal / FX / crossfader normalmente.
8. Mientras Spotify suena, prepara la siguiente pista local normal de Mixxx.
9. Carga una pista normal sobre `spotify-silence.mp3` cuando termines.

Cuando la centinela desaparece del deck proxy: la repetición se apaga, Spotify se pausa, AUX1 se reinicia/desactiva y el deck vuelve a la operación normal.

---

# Si cargas accidentalmente la centinela en ambos decks

Solo existe una fuente de Spotify, así que solo un deck puede controlarla. El script protege contra la carga de la centinela en ambos decks: el proxy activo conserva la propiedad, la segunda centinela se ignora, y si ambos están cargados al iniciar el script, gana el Deck 1.

---

# Solución de problemas

## Python dice que no encuentra `SpotifyMixxx`

```text
Could not find MIDI input containing "SpotifyMixxx"
```

- **Windows:** asegúrate de que loopMIDI esté en ejecución y que exista el puerto `SpotifyMixxx`.
- **macOS:** comprueba Configuración Audio MIDI → Estudio MIDI → IAC Driver, que el puerto exista y esté en línea.
- **Linux:** comprueba `aconnect -l` para ver el puerto virtual, y que la entrada MIDI del puente coincida.

Reinicia el puente de Python después de crear/renombrar el puerto.

## Mixxx no muestra el dispositivo MIDI virtual

Cierra y reinicia Mixxx después de crear el puerto. Luego mira `Preferencias -> Controladores`.

## Python funciona manualmente pero no recibe nada de Mixxx

Busca en el log de Mixxx `[SpotifyMixxx] initializing` y `[SpotifyMixxx] ready`. Si el script no carga:

- confirma que ambos archivos están en la carpeta de controladores de usuario de Mixxx
- confirma que `SpotifyMixxx.midi.xml` referencia a `SpotifyMixxx.js`
- confirma que el dispositivo MIDI virtual tiene seleccionado y habilitado el mapeo `SpotifyMixxx`

## El backend no se importa

- **Windows:** `ModuleNotFoundError: libspotifyctl` → ejecuta `python -m pip install libspotifyctl`
- **Linux:** `ModuleNotFoundError: dbus` → ejecuta `python -m pip install dbus-python`
- **Windows/Linux con estado "unknown":** el backend no pudo leer el estado de Spotify — asegúrate de que Spotify esté en ejecución y haya reproducido audio al menos una vez.

## Spotify está reproduciendo pero no lo oyes

Comprueba la ruta de audio en orden:

```text
Spotify
 -> salida de audio virtual (VB-Cable / BlackHole / monitor null-sink)
 -> Auxiliar 1 de Mixxx
 -> Master de Mixxx
```

Activa AUX1 manualmente en Mixxx y comprueba si su medidor se mueve.

## Oigo Spotify independientemente del crossfader

El script espera que AUX1 participe en la mezcla principal de Mixxx usando `[Auxiliary1],main_mix` y establece `orientation = 0` para Deck 1 / `2` para Deck 2. Asegúrate de usar el `SpotifyMixxx.js` suministrado.

## Linux: `os.Volume` no cambia

Spotify puede no exponer un `Volume` escribible en todas sus versiones. El puente lo maneja con elegancia, pero el control de volumen depende del soporte MPRIS de Spotify; el transporte (play/pause/cue/seek/next/previous) siempre funciona.

## La centinela tarda mucho en cargar

Usa la receta suministrada de 10 segundos / -90 dB. No uses archivos largos ni de silencio absoluto.

## El volumen de Spotify se detiene en la ganancia de unidad

Esto es intencional. La ganancia del deck se mapea al volumen de aplicación 0–100 de Spotify; las pregains del deck por encima de la unidad se limitan a 100. El fader de canal se sigue manejando a través de AUX1 en Mixxx.

---

# Archivos en este repositorio

```text
spotify_bridge.py
```

Detecta automáticamente el SO y ejecuta el puente. Escucha el puerto MIDI virtual `SpotifyMixxx` y traduce los comandos al backend correspondiente.

```text
spotify_backends/
  base.py       # interfaz común
  windows.py    # libspotifyctl (SMTC / Core Audio)
  macos.py      # AppleScript
  linux.py      # D-Bus MPRIS
```

Backends de control de Spotify específicos por SO.

```text
SpotifyMixxx.js
```

Lógica del lado de Mixxx (independiente de la plataforma). Detecta la centinela, observa los Deck 1/2, refleja el enrutado en AUX1 y envía transporte/volumen por MIDI.

```text
SpotifyMixxx.midi.xml
```

Mapeo de controlador virtual cuyo propósito principal es cargar `SpotifyMixxx.js` para el dispositivo MIDI virtual.

```text
requirements.txt
```

Dependencia base (`python-rtmidi`); los backends por plataforma están documentados en el archivo.

---

# Protocolo MIDI

El puente usa intencionadamente un protocolo MIDI privado y pequeño:

```text
Note 16, velocity > 0  -> Spotify PLAY
Note 17, velocity > 0  -> Spotify PAUSE
Note 18, velocity > 0  -> Spotify CUE
CC 32, value 0..127    -> volumen de Spotify 0..100
```

Esto es solo comunicación entre `SpotifyMixxx.js` y `spotify_bridge.py`.

---

# Limitaciones

Esto no es soporte nativo de Spotify en Mixxx. No tienes:

- forma de onda de Spotify en Mixxx
- análisis de BPM/clave de Spotify en el deck proxy
- sincronización de beats contra la pista de Spotify
- scratching
- hotcues para Spotify
- búsqueda automática de Spotify desde Mixxx
- metadatos de la pista de Spotify dentro del deck proxy

El objetivo es deliberadamente menor: hacer que una canción de Spotify solicitada ocasionalmente sea fácil de poner en cue, monitorizar y hacer transición dentro de un set normal de Mixxx.

---

# Privacidad y seguridad

El puente:

- solo escucha un dispositivo MIDI local
- controla la app local de Spotify usando backends nativos del SO (AppleScript / SMTC / D-Bus)
- no requiere credenciales de la API de Spotify
- no requiere OAuth
- no contiene una contraseña de Spotify
- no contacta con un servidor personalizado

La autenticación de Spotify permanece enteramente dentro de la aplicación oficial de Spotify.

---

# Términos legales / de servicio

Este es un proyecto comunitario no oficial y no está afiliado con Spotify, Mixxx, Microsoft, Apple ni con ningún proveedor de audio/MIDI virtual.

No elude el DRM de Spotify ni crea copias descargables de pistas de Spotify.

Eres responsable de cumplir los términos de Spotify y cualquier requisito de licencia musical/actuación pública que se aplique a dónde y cómo lo usas.

---

# Referencias

- Manual de Mixxx: https://manual.mixxx.org/
- Scripting MIDI de Mixxx: https://github.com/mixxxdj/mixxx/wiki/midi-scripting
- loopMIDI (MIDI virtual en Windows): https://www.tobias-erichsen.de/software/loopmidi.html
- VB-Audio Cable (audio virtual en Windows): https://vb-audio.com/Cable/
- libspotifyctl (control de Spotify en Windows): https://pypi.org/project/libspotifyctl/
- Apple IAC Driver: https://support.apple.com/guide/audio-midi-setup/transfer-midi-information-between-apps-ams1013/mac
- BlackHole (audio virtual en macOS): https://github.com/ExistentialAudio/BlackHole
- MPRIS (interfaz de reproductor multimedia de Linux): https://specifications.freedesktop.org/mpris-spec/latest/

---

# Licencia

MIT
