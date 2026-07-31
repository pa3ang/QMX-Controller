# PA3ANG QMX Control & Support Program
## Version 1.0 (July 2026)

---

## 1. Introduction

The QMX Control & Support Program is a Python/Tkinter desktop application for controlling QMX transceivers over CAT (Computer Aided Transceiver) commands.

- Originally developed in April 2025 for the **Radio-Kits Explorer** 20m transceiver.
- Later adapted for the **QRP-Labs QMX** and **QMX+**, since these share the same Kenwood TS-480-based CAT protocol.
- Works on any operating system, since the source is Python and the GUI is built with the platform-independent Tkinter toolkit.

### Main features
- Frequency, mode, band and RF Gain control
- 4 fixed memory buttons plus a variable **Extra Memories** drop-down
- 4 programmable CW messages (one reserved for your callsign) plus a free-text CW entry field
- **TUNE** button for antenna tuning
- **RBN Spots** window — shows Reverse Beacon Network reports of your own CQ calls
- **DX Cluster** window — shows DX spots filtered to your QMX model's frequency range, with click-to-tune and QSO logging
- **SPOTS** window - shows POTA, SOTA, WWFF spots based on a filter in the qmx.ini file , with click-to-tune and QSO logging
- Integration with **Cloudlog** for automatic QSO logging
- S meter and Power meter integration

---

## 2. Requirements

- Python 3 with Tkinter (already included in most Python installations)
- A serial connection to the transceiver (USB CAT cable)
- Internet access for the RBN and DX Cluster features
- A Cloudlog installation (optional, only needed if you want automatic logging)

### Required files

| File | Purpose |
|---|---|
| `qmx.ini` | All user-specific settings (required on every platform) |
| `qmx.py` | QMX serial/CAT communication class |
| `dxcluster.py` | DX Cluster network class |
| `rbnetwork.py` | RBN network class |
| `tooltip.py` | Tooltip helper for the CW message buttons |
| `cloudlog.py` | Cloudlog logging API class |
| `spotsnetwork` | Connection to POTA, SOTA and WWFF |

**Windows users:** an executable (.exe) version is available. You only need to keep `qmx.ini` alongside the executable — the other `.py` files are already bundled in.

**Linux/macOS users:** keep all files listed above together in the same folder as the main script.

---

## 3. Installation

1. Copy all program files into one folder.
2. Edit `qmx.ini` (see Section 4) to match your station, transceiver model, and preferences.
3. Connect your transceiver via USB and note the serial port name (e.g. `COM5` on Windows, `/dev/ttyUSB0` on Linux).
4. Start the program:
   - Windows: double-click the `.exe`
   - Linux/macOS: run `python3 main.py` from the folder

If `qmx.ini` is missing or incomplete, the program will fail to start, since all key settings are read from it at launch.

---

## 4. Configuration file: `qmx.ini`

The `.ini` file is divided into sections. All of them are required.

### `[QMX]`
```
model = Plus
```
Sets your transceiver model. Valid values: `LOW`, `MID`, `HIGH`, `PLUS` (case-insensitive). This determines the tunable frequency range:

| Model | Frequency range |
|---|---|
| LOW | 3,500 – 14,350 kHz (80m–20m) |
| MID | 5,000 – 21,450 kHz (60m–15m) |
| HIGH | 14,000 – 30,000 kHz (20m–10m) |
| PLUS | 1,800 – 54,000 kHz (160m–6m) |

### `[Serial]`
```
port = COM5
```
The serial port your transceiver is connected to.

### `[Messages]`
```
callsign  = PA3ANG
message_1 = R UR 55N 55N OP JOHAN 73
literal_1 = REPORT
message_2 = TU
literal_2 = TU
cq        = CQ CQ DE PA3ANG PA3ANG K
```
- `callsign` — used on the first CW button, and also for RBN searches and DX Cluster login.
- `message_1` / `message_2` — the actual CW text sent by buttons 2 and 3.
- `literal_1` / `literal_2` — the short text shown **on** those buttons (the full message shows as a tooltip on hover).
- `cq` — text sent by the CQ button.

### `[Memories]`
```
fixed = 3630,LSB;7073,LSB;14060,CW;14292,USB
extra = 3573,CW;10136,DIGI; ...
```
Each entry is `frequency(kHz),mode`, separated by semicolons.
- `fixed` — fills the 4 fixed memory buttons (in order).
- `extra` — fills the **Extra Memories** drop-down menu, useful for additional frequencies that don't need a dedicated button.

### `[ModeColors]`
```
map = CW: #0FF40B; USB: lightblue; LSB: lightblue; AM: orange; DIGI: #0B80F4
```
Assigns a background color to memory buttons based on mode, for quick visual recognition.

### `[Bandplan]`
```
80m = 3500,3600,CW;3600,3800,LSB
40m = 7000,7040,CW;7040,7200,LSB
...
```
Defines band edges and the default mode to use in each frequency sub-range. This is used to:
- Populate the **Band** drop-down (only bands within your model's range are listed)
- Automatically determine the mode when tuning to a DX Cluster spot
- Look up the band name when logging a QSO to Cloudlog

### `[DXCluster]`
```
servers =
    	dxc.pi4cc.nl,8000
    	dxcluster.iu1bow.it,7300
    	dx1.g5gdx.com,7300
    	dxc.hamserve.uk,7300
call = ${Messages:callsign}
```
Your preferred DX Cluster server and alternatives plus the callsign used to log in.

### `[Filters]`
```
commands =
    clear/spots all
    accept/spots on hf and by_zone 14,15,16

```
A list of cluster filter/setup commands (one per line) sent automatically after login.

### `[RBNetwork]`
```
host = telnet.reversebeacon.net
port = 7000
```
Reverse Beacon Network telnet server used to fetch spots of your own CQ calls.

### `[Spots]`
```
bands    = 15,20,40
modes    = CW,SSB
max_age  = 15
europe   = True
```
POTA, SOTA, WWFF spots running through hardcoded API url's

### `[Cloudlog]`
```
URL      = https://yourcloudlog.example.com
APIKey   = xxxxxxxxxxxxxxxx
StationID = 1
```
Your Cloudlog instance details, used for one-click QSO logging from the DX Cluster window.

---

## 5. The Main Window

The window title bar shows the program version and your configured QMX model.

### Top row
| Control | Function |
|---|---|
| **Frequency field** | Shows/sets the current VFO frequency in kHz. Type a value and press **Enter** to tune. |
| **Mode drop-down** | Select LSB, USB, CW, AM, or DIGI. |
| **Band drop-down** | Select a band; automatically tunes to that band using its default sub-range. |
| **S/Power Meter** | Shows receive signal in S points or RF power in Watt |

### Right column
| **CW buttons (right side)** | Callsign, Message 1, Message 2, and CQ — sends the configured CW text at the press of a button. Hover over a button to see the full message as a tooltip. |

### Memory row
| **Four buttons** | One button per entry in `[Memories] fixed`. Each button is color-coded by mode (see `[ModeColors]`) and, when clicked, instantly sets the transceiver to that frequency and mode. |
| **Extra memories** | In a drop-down menu, configured under `[Memories] extra` and colored by mode as well. |

### Manual CW entry
A text field below the memory buttons lets you type any custom CW message and send it by pressing **Enter**. It shows placeholder text ("Type here you cw message [enter]") until you click into it.

> **Note:** the CW buttons, the manual CW entry field, and the RBN window are only active (colored/enabled) while the transceiver is in **CW mode**. In any other mode they are grayed out and disabled.

### RBN Spots window
Displays live Reverse Beacon Network reports of your own CQ calls — useful for checking your signal reports across the world in real time. The list has a scroll option.

### DX Cluster window
Displays DX spots filtered so that only spots within your QMX model's supported frequency range are shown (FT8/FT4 digital spots are filtered out automatically).

### Spots window
Displays POTA, SOTA, WWFF spots filtered based on the qmx.ini entry [Spots] so that only spots within your interest are shown.

For both 
| Action | Result |
|---|---|
| **Double-click (left)** a spot | Tunes the transceiver to that spot's frequency and sets the correct mode from the bandplan. |
| **Single-click (right)** a spot | Opens the spotted station's QRZ.com page in your web browser. |

### Botton line
| Control | Function |
|---|---|
| **Log QSO** | The last double-cliked spot line will be logged including Callsign, Frequency=Band, Mode, SOTA,POTA,WWFF (optional) with comment QMX-Controller. |
| **RF GAIN** adjust | With the slider the RF Gain can be changed. The QMX will always change to the default value (from it's internal band configuration) when changing band. |
| **TUNE** | With this button you can put the QMX in SWR measurement. All comms are stopped and the button turns red. Click again to exit. |

---

## 6. Typical Workflow

1. Start the program — it connects to the transceiver, DX Cluster, and RBN automatically.
2. Watch the DX Cluster window for connecting.
3. The Spots window will start (turning the literals SOTA, POTA and WWFF green) and will start showing spots.  
4. Double-click a spot to instantly QSY and set the correct mode.
5. Work the station, then right double-click the spot to log it to Cloudlog with one confirmation click.
6. When calling CQ in CW, use the CQ button, then watch the RBN window for reports of your signal.

---

## 7. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Program won't start / crashes immediately | `qmx.ini` missing, malformed, or missing a required section |
| No frequency/mode updates from the radio | Wrong serial port in `[Serial]`, or cable/driver issue |
| CW buttons stay grayed out | Transceiver is not in CW mode — switch mode first |
| No DX, POTA or RBN spots appear | Check `[DXCluster]` / `[RBNetwork]` host and port, and your internet connection |
| QSO logging fails | Check `[Cloudlog]` URL and API key |
| Band drop-down is empty or missing bands | Check that `[Bandplan]` entries fall within your configured QMX model's frequency range |

---

## 8. File Summary (Linux/macOS)

```
project-folder/
├── qmx.ini        (your settings — edit this)
├── main.py        (this program)
├── qmx.py         (QMX CAT communication)
├── dxcluster.py   (DX Cluster network client)
├── rbnetwork.py   (RBN network client)
├── tooltip.py     (button tooltips)
└── cloudlog.py     (Cloudlog logging API)
```

Windows users only need the `.exe` and `qmx.ini`.

---

