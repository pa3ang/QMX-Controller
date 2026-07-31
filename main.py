# PA3ANG V1.0  July 2026
# Made on Windows (the Tkinter GUI script is platform independent) but can be used on all operating systems.
#
# The original idea of this program dates back to April 2025 and was developed to support the Radio-Kits Explorer 20 meter transceiver.
# Later it was adapted for the QRP-Labs QMX and QMX+ transceivers, as they use the same CAT protocol based on the Kenwood TS-480.
#
# During development, the program evolved into a much more sophisticated Python application with several class modules and an .ini file
# to customize user settings.
#
# The main functionality is frequency and mode control.
# Additional features include an RBN report window showing your own CQ spots and a DXCluster window displaying DX spots within the
# supported frequency range of the connected QMX model.
#
# The program contains 12 fixed memory buttons and a variable Extra Memories drop-down menu.
#
# For CW operation, four programmable messages are available. One of these is reserved for your callsign and is also used for
# RBN searches and DXCluster login.
# A manual CW message entry is also available through a dedicated input field in the GUI.
#
# The spots in the DXCluster window can be double-clicked to tune the QMX.
# Both the RBN and DXCluster windows are scrollable.
#
# Additional files (Linux version):
#   - qmx.ini       - all user-specific parameters are stored here
#   - qmx.py        - QMX communication class
#   - dxcluster.py  - DXCluster class
#   - cloudlog.py   - Hook into cloudlog
#   - rbnetwork.py  - RBN network class
#   - tooltip.py    - Message shown when hoover CW buttons 
#   - spotnetwork.py- SOTA, POTA, WWFF spots
#
# For Windows, an executable version is available and only requires the qmx.ini file.

import configparser
import threading
import sys
import os
import re
import queue
import webbrowser
from tkinter import *
from tkinter import ttk, IntVar, StringVar
from tkinter import messagebox
from dxcluster import DXCluster
from rbnetwork import RBNetwork
from qmx import QMX
from tooltip import ToolTip
from cloudlog import Cloudlog
from spotnetwork import POTA, SOTA, WWFF

# Initialise Tkinter window
window = Tk()
style = ttk.Style()
style.theme_use("clam")

# ---------------------------- LOAD INI FILE AND READ ALL USER SET PARAMTERS ----------------------------------------
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation()
)
config.read(os.path.join(base_path, "qmx.ini"))

QMX_MODEL = config.get("QMX", "model", fallback="Plus")

# connect qmx
qmx = QMX(config['Serial']['port'], model=QMX_MODEL)

# GUI variables
rf_gain_value = IntVar(value=qmx.get_rf_gain())
rf_gain_display = StringVar(value=f"{qmx.get_rf_gain()} dB")

# CW Messages and button literal
CALLSIGN = config['Messages']['callsign']
MESSAGE_1 = config['Messages']['message_1']
LITERAL_1 = config['Messages']['literal_1']
MESSAGE_2 = config['Messages']['message_2']
LITERAL_2 = config['Messages']['literal_2']
CQ = config['Messages']['cq']

# Memory list
fixed_str = config['Memories']['fixed']
FIXED_MEMORIES = []
for item in fixed_str.split(';'):
    if item.strip():
        freq, mode = item.split(',')
        FIXED_MEMORIES.append(
            (int(freq), mode.strip())
        )

extra_str = config['Memories']['extra']
EXTRA_MEMORIES = []
for item in extra_str.split(';'):
    if item.strip():
        freq, mode = item.split(',')
        EXTRA_MEMORIES.append(
            (int(freq), mode.strip())
        )

# Mode colors
color_str = config['ModeColors']['map']
MODE_COLOR = {}
for item in color_str.replace("\n", "").split(';'):
    if item.strip():
        key, value = item.split(':')
        MODE_COLOR[key.strip()] = value.strip()

# Modes available in the QMX
MODES = (
    "LSB",
    "USB",
    "CW",
    "AM",
    "DIGI"
)
  
QMX_RANGES = {
    "LOW":  (3500,  14350),   # 80m - 20m
    "MID":  (5000,  21450),   # 60m - 15m
    "HIGH": (14000, 30000),   # 20m - 10m
    "PLUS": (1800,  54000),   # 160m - 6m
}
QMX_MIN_FREQ, QMX_MAX_FREQ = QMX_RANGES.get(QMX_MODEL.upper(), QMX_RANGES["MID"])

BANDPLAN = []
BAND_LIST = []
for band, value in config["Bandplan"].items():
    band_added = False

    for entry in value.split(";"):
        start, end, mode = entry.split(",")
        start = int(start)
        end = int(end)
        mode = mode.strip().upper()

        BANDPLAN.append((start, end, mode))

        if not band_added and QMX_MIN_FREQ <= start <= QMX_MAX_FREQ:
            BAND_LIST.append(band)
            band_added = True
       
# Initialize DX Cluster
servers=[]
for line in config.get("DXCluster","servers").splitlines():
    line=line.strip()
    if line:
        host,port=line.split(",")
        servers.append((host,int(port)))
DX_CALL = config["DXCluster"].get("call")
DX_FILTERS = [
    x.strip()
    for x in config["DXFilters"]["commands"].splitlines()
    if x.strip()
]

# Get RBN host and port
RBN_HOST = config["RBNetwork"].get("host")
RBN_PORT = config["RBNetwork"].getint("port")

# Filters for SOTA, POTA, WWFF
all_spots = {}
SPOT_BANDS = tuple(
    x.strip()
    for x in config["Spots"]["bands"].split(",")
)
SPOT_MODES = tuple(
    x.strip().upper()
    for x in config["Spots"]["modes"].split(",")
)
SPOT_MAX_AGE = config["Spots"].getint("max_age")
SPOT_EUROPE = config["Spots"].getboolean("europe")

# connect logbook  (in my case Cloudlog)
cloudlog = Cloudlog(
    config.get("Cloudlog", "URL"),
    config.get("Cloudlog", "APIKey"),
    config.get("Cloudlog", "StationID")
)

# ---------------------------- INITIALISE AND DEFINE GLOBAL VARIABLES ----------------------------------------------
# Configure and create Tkinter screen
window.geometry("604x840")
window.configure(bg="#202020")
window.wm_title(f"QMX Control & Support Program V1.0  ||  QMX Model: {QMX_MODEL}")

# Global variables
last_frequency 		= 0 
last_mode           = "USB" 
current_mode        = StringVar(value="USB")
dx_queue            = queue.Queue()
spot_queue          = queue.Queue()
band_var            = StringVar(value="BAND")
tune_state          = False
log_button_text      = StringVar(value="Log QSO with ---")
current_tuned_spot  = None
rf_gain_dragging    = False

# ---------------------------- FUNCTIONS AND SUBROUTINES (SOME HARDCODED) ----------------------------------------
# Funtions 
def serial_read():
    global last_frequency, last_mode

    freq = qmx.get_freq()
    if freq and freq != last_frequency:
        last_frequency = freq
        entry_frequency.delete(0, END)
        entry_frequency.insert(0, f"{freq/1000:.2f}")

    mode = qmx.get_mode()
    if mode and mode != last_mode:
        last_mode = mode
        current_mode.set(mode)
        update_band_menu()
        update_cw_button()

    bn = qmx.get_band()
    if bn is not None:
        for band, number in qmx.BANDS[qmx.model].items():
            if number == bn:
                band_var.set(band)
                break  
    if not rf_gain_dragging:
        gain = qmx.get_rf_gain()
        if int(round(rf_gain_scale.get())) != gain:
            rf_gain_scale.set(gain)
            rf_gain_display.set(f"{gain} dB")

def set_direct_frequency():
    try:
        freq_khz = float(entry_frequency.get())	            # Read frequency as float (bijv. 7073.5)
        freq_hz = int(freq_khz * 1000)  	                # Translate to Hz 
        if QMX_MIN_FREQ <= freq_khz <= QMX_MAX_FREQ:  	    # Check range roughly
            set_frequency(freq_hz)
        else:
            print("Fout: Frequentie buiten bereik.")
    except ValueError:
        print("Fout: Ongeldige invoer, voer een geldig getal in.")
              
def set_frequency(frequency): 
    qmx.set_freq(int(frequency))
    # fast GUI update
    entry_frequency.delete(0, END)
    entry_frequency.insert(0, f"{frequency/1000:.2f}")

def set_mode(selected_mode): 
    qmx.set_mode(selected_mode)

def set_memory(frequency, mode):
    set_frequency(frequency * 1000)
    set_mode(mode)

def update_cw_button():
    enabled = current_mode.get() == "CW"
    mode_color = MODE_COLOR.get(current_mode.get(), "lightgrey")

    for button in cw_buttons:
        button.config(bg=mode_color if enabled else "lightgrey",state="normal" if enabled else "disabled")

    if enabled:
        custom_cw_entry.config(bg=mode_color,fg="grey",state="normal")
        rbn_label.config(fg="white")
        rbn_list.config(fg="black")
    else:
        custom_cw_entry.config(bg=mode_color,fg="grey",state="disabled")
        rbn_label.config(fg="grey")
        rbn_list.config(fg="grey")

def send_cw_message(message):
    qmx.send_cw_message(message)

def send_custom_cw():
    text = custom_cw_entry.get().strip()
    if not text:
        return
    send_cw_message(text)
    custom_cw_entry.delete(0, END)
    custom_cw_entry.insert(0, " ")
    custom_cw_entry.icursor(1)
    custom_cw_entry.focus_set()

def update_band_menu():
    menu = band_dropdown["menu"]
    menu.delete(0, "end")

    for band in BAND_LIST:
        menu.add_command(
            label=band,
            command=lambda b=band: (band_var.set(b), set_band(b))
        )

def set_band(band):
    qmx.set_band(band)

def bandplan_lookup(freq):
    for start, end, mode in BANDPLAN:
        if start <= freq <= end:
            return mode
    return None

def band_lookup(freq):
    for band, value in config["Bandplan"].items():
        for entry in value.split(";"):
            start, end, mode = entry.split(",")
            if int(start) <= freq <= int(end):
                return band.upper()
    return None

# Automatic update forever routine
def update_status():
    serial_read()
    window.after(200, update_status)

# RBN functions 
def start_rbn():
    global rbn
    rbn = RBNetwork(
        CALLSIGN,
        host=RBN_HOST,
        port=RBN_PORT,
        callback=lambda line: window.after(0, update_rbn, line)
    )
    rbn.start()

def update_rbn(line):
    rbn_list.insert(0, " " + line)
    rbn_list.yview_moveto(0)

# SOTA, POTA, WWFF functions
spot_states={"SOTA":"DISCONNECTED","POTA":"DISCONNECTED","WWFF":"DISCONNECTED"}
def start_spots():
    global pota,sota,wwff

    pota = POTA(
        source="POTA",
        callback=lambda s: window.after(0,spot_received,s),
        status_callback=spot_status,
        bands=SPOT_BANDS,
        modes=SPOT_MODES,
        max_age=SPOT_MAX_AGE,
        europe=SPOT_EUROPE,
        interval=60
    )

    sota = SOTA(
        source="SOTA",
        callback=lambda s: window.after(0,spot_received,s),
        status_callback=spot_status,
        bands=SPOT_BANDS,
        modes=SPOT_MODES,
        max_age=SPOT_MAX_AGE,
        europe=SPOT_EUROPE,
        interval=60
    )

    wwff = WWFF(
        source="WWFF",
        callback=lambda s: window.after(0,spot_received,s),
        status_callback=spot_status,
        bands=SPOT_BANDS,
        modes=SPOT_MODES,
        max_age=SPOT_MAX_AGE,
        europe=SPOT_EUROPE,
        interval=60
    )

    wwff.connect()
    pota.connect()
    sota.connect()

def spot_status(source,status):
    spot_states[source]=status
    window.after(0,update_spot_label)
    
def update_spot_label():
    colors={"CONNECTED":"green","ERROR":"red","DISCONNECTED":"grey"}
    spot_label.config(state="normal")
    spot_label.tag_config("sota",foreground=colors.get(spot_states["SOTA"],"grey"))
    spot_label.tag_config("pota",foreground=colors.get(spot_states["POTA"],"grey"))
    spot_label.tag_config("wwff",foreground=colors.get(spot_states["WWFF"],"grey"))
    spot_label.config(state="disabled")

def spot_received(spot):
    key = f"{spot['source']}:{spot['call']}:{spot['freq']}"
    all_spots[key] = spot

def update_spot_window():
    # huidige scrollpositie bewaren
    yview = spot_list.yview()
    spot_list.delete(0,END)
    spot_list.freq={}
    spot_list.spots={}
    spots = list(all_spots.values())
    spots.sort(
        key=lambda x:x["age"]
    )
    for index,spot in enumerate(spots):
        freq = spot["freq"]/1000
        line = (
            f" {spot['source']:9}"
            f"{freq:8.2f}    "
            f"{spot['mode']:8}"
            f"{spot['call']:16}"
            f"{spot['ref']:16}"
            f"{spot['age']:>3} min"
        )
        spot_list.insert(
            END,
            line
        )
        color={
            "POTA":"black",
            "SOTA":"red",
            "WWFF":"green"
        }.get(
            spot["source"],
            "white"
        )
        spot_list.itemconfig(
            index,
            fg=color
        )
        spot_list.spots[index]=spot
        spot_list.freq[index]=freq

    # oude scrollpositie herstellen
    spot_list.yview_moveto(yview[0])
    window.after(1000,update_spot_window)

# DX Cluster functions 
def start_dxcluster():
    #global cluster
    cluster = DXCluster(
        servers=servers,
        call=DX_CALL,
        filters=DX_FILTERS,
        callback=lambda line: window.after(0, dx_spot_received, line),
        status_callback=dx_status
    )   
    threading.Thread(
        target=cluster.connect,
        daemon=True
    ).start()

current_spot = {
    "call": None,
    "freq": None,
    "mode": None
}

def dx_status(connected,host,port):
    window.after(0,lambda:update_dx_label(connected,host,port))

def update_dx_label(connected,host,port):
    color="green" if connected else "lightgrey"

    dx_label.config(state="normal")
    dx_label.delete("1.0","end")
    dx_label.insert("end","DX Cluster : ")
    dx_label.insert("end",host,"host")
    dx_label.insert("end"," - ")
    dx_label.insert("end", DX_FILTERS[-1], "filter")
    dx_label.tag_config("host",foreground=color)
    dx_label.config(state="disabled")

def search_qrz(event):
    widget = event.widget
    index = widget.nearest(event.y)
    if index < 0:
        return
    call = None
    if widget == dx_list:
        line = widget.get(index)
        m = re.search(r"\s\d+\.\d+\s+([A-Z0-9/]+)", line)
        if m:
            call = m.group(1)
    elif widget == spot_list:
        spot = widget.spots.get(index)
        if spot:
            call = spot["call"]
    if call:
        webbrowser.open(f"https://www.qrz.com/db/{call}")

def log_tuned_qso():
    if current_tuned_spot is None:
        return
    if not messagebox.askyesno(
        "Log QSO",
        f"QSO met {current_tuned_spot['call']} in Cloudlog loggen?"
    ):
        return
    spot = current_tuned_spot
    band = band_lookup(
        spot["freq"]/1000
    )
    if band is None:
        return
    mode = spot["mode"].upper()
    if spot["spot_ref"] in ("SOTA","POTA","WWFF"):
        rst = "559" if mode == "CW" else "55"
    else:
        rst = "599" if mode == "CW" else "59"

    cloudlog.log_qso(
        call=spot["call"],
        freq=spot["freq"]/1000,
        band=band,
        mode=mode,
        rst_sent=rst,
        rst_rcvd=rst,
        comment="QMX Controller",
        activity=spot["spot_ref"],
        reference=spot["ref"]
    )

def tune_dxcluster_spot(event):
    global current_tuned_spot
    index = dx_list.nearest(event.y)
    if index < 0:
        return
    line = dx_list.get(index)
    freq = dx_list.freq.get(index)
    if not freq:
        return
    mode = bandplan_lookup(freq)
    if mode is None:
        return
    call = re.search(
        r"\s\d+\.\d+\s+([A-Z0-9/]+)",
        line
    )
    if not call:
        return
    dx_call = call.group(1)
    set_frequency(int(freq * 1000))
    set_mode(mode)
    current_tuned_spot = {
        "spot_ref": "DX Cluster",
        "call": dx_call,
        "freq": int(freq * 1000),
        "mode": "SSB" if mode in ("USB","LSB") else mode,
        "ref": ""
    }
    log_button_text.set(
        f"Log QSO met {dx_call}"
    )

def update_dx_window():
    while not dx_queue.empty():
        display, freq = dx_queue.get()
        dx_list.insert(
            END,
            display
        )
        # frequentie bewaren bij de regel
        dx_list.freq = getattr(dx_list, "freq", {})
        dx_list.freq[dx_list.size()-1] = freq
        dx_list.see(END)
    window.after(200, update_dx_window)

def dx_spot_received(line):
    if line.startswith("~~~ "):
        dx_queue.put((line[3:], None))
        return
    # Ignore non-spot lines
    if not line.startswith("DX de"):
        return
    # Ignore digital mode spots if mentioned as such in the comment
    upper = line.upper()
    if "FT8" in upper or "FT4" in upper:
        return
    # Extract frequency from spot
    match = re.search(r"\s(\d+\.\d+)\s", line)
    if not match:
        return
    freq_khz = float(match.group(1))
    # Accept only spots for QMX model (low, mid, high, plus)
    if freq_khz < QMX_MIN_FREQ or freq_khz > QMX_MAX_FREQ:
        return
    # Valid spot found get mode according to bandplan
    mode = bandplan_lookup(freq_khz)
    if mode is None:
        return
    # Remove unwanted characters bell, starting literal and :
    line = line.replace("\x07", "")
    line = line.replace("DX de ", " ") 
    line = line.replace(":", "", 1) 
    # Finally put spot in the queue for display
    dx_queue.put((line, freq_khz))

def tune_spot(event):
    global current_tuned_spot
    index = spot_list.nearest(event.y)
    if index < 0:
        return
    spot = spot_list.spots.get(index)
    if not spot:
        return
    freq = spot["freq"]
    freq_khz = freq / 1000
    if freq_khz < QMX_MIN_FREQ or freq_khz > QMX_MAX_FREQ:
        return
    mode = bandplan_lookup(freq_khz)
    if mode is None:
        return
    set_frequency(freq)
    set_mode(mode)
    current_tuned_spot = {
        "spot_ref": spot["source"],
        "call": spot["call"],
        "freq": freq,
        "mode": "SSB" if mode in ("USB","LSB") else spot["mode"],
        "ref": spot["ref"]
    }
    log_button_text.set(
        f"Log QSO met {spot['call']}"
    )

def toggle_tune():
    global tune_state
    if tune_state:
        qmx.tune_off()
        tune_button.config(bg="lightgrey")
    else:
        qmx.tune_on()
        tune_button.config(bg="red")
    tune_state = not tune_state

def update_smeter():
    smeter_canvas.delete("all")
    bw, bh, sp = 8, 12, 3
    total = 11 * (bw + sp) - sp
    start_x = (int(smeter_canvas["width"]) - total) // 2
    if qmx.is_tx():
        try:
            power = qmx.get_power()
        except:
            power = 0
        level = min(10, max(0, int(power * 2 + 0.5)))
        labels = {0:"0", 2:"1", 4:"2", 6:"3", 8:"4", 10:"5W"}
    else:
        try:
            level = qmx.get_smeter()
        except:
            level = 0
        labels = {0:"0", 2:"3", 4:"5", 6:"7", 8:"9", 10:"+20"}
    # Draw bargraph
    for i in range(11):
        x = start_x + i * (bw + sp)
        if i < 3:
            color = "orange"
        elif i < 9:
            color = "green"
        else:
            color = "red"
        if i >= level:
            color = window.cget("bg")
        smeter_canvas.create_rectangle(x, 5, x + bw, 3 + bh,fill=color,outline="")
    # Draw scale
    for pos, text in labels.items():
        x = start_x + pos * (bw + sp) + bw / 2
        smeter_canvas.create_text(x, 24,text=text,fill="white",font=("Consolas", 7))

    window.after(100, update_smeter)

def rf_gain_press(event):
    global rf_gain_dragging
    rf_gain_dragging = True


def rf_gain_move(value):
    gain = int(round(float(value)))
    rf_gain_display.set(f"{gain} dB")


def rf_gain_release(event):
    global rf_gain_dragging
    rf_gain_dragging = False

    gain = int(round(rf_gain_scale.get()))
    qmx.set_rf_gain(gain)

def clear_placeholder(event): 
    if custom_cw_entry.get() == " " + CW_PLACEHOLDER:
        custom_cw_entry.delete(0, END)
        custom_cw_entry.insert(0, " ")      # linker marge
        custom_cw_entry.icursor(1)          # cursor achter de spatie
        custom_cw_entry.config(fg="black")

def add_placeholder(event):
    if custom_cw_entry.get().strip() == "":
        custom_cw_entry.delete(0, END)
        custom_cw_entry.insert(0, " " + CW_PLACEHOLDER)
        custom_cw_entry.config(fg="grey")

# ---------------------------- GUI, BUTTONS AND INFO SCREENS ----------------------------------------
# Create compact screen based on Python Tkinter / Windows 11 Python 3
spacer = Frame(window, height=20, bg=window.cget("bg"))
spacer.grid(row=0, column=0, columnspan=6)
# Input for direct frequency
entry_frequency = Entry(window, width=10, font=('Arial', 20), justify='center', bg=window.cget("bg"), fg="yellow",relief="flat", highlightthickness=0, bd=0)
entry_frequency.grid(column=0, row=1, padx=(14,5), columnspan=2)
entry_frequency.bind("<Return>", lambda event: set_direct_frequency())

# Mode drop-down menu
mode_menu = OptionMenu(window, current_mode, *MODES, command=set_mode)
mode_menu.config(bg="lightgrey", activebackground="lightgrey", width=4, font=("Consolas", 10), relief="flat", highlightthickness=0, bd=2)
mode_menu["menu"].config(bg="lightgrey", font=("Consolas", 10))
mode_menu.grid(column= 2, row=1, padx=2)

band_dropdown = OptionMenu(window, band_var, *BAND_LIST, command=set_band)
band_dropdown.config(width=4, bg="lightgrey", activebackground="lightgrey", font=("Consolas", 10),relief="flat", highlightthickness=0, bd=2)
band_dropdown["menu"].config(bg="lightgrey", font=("Consolas", 10))
band_dropdown.grid(row=1, column=3, padx=2)

# S-meter balk
smeter_canvas = Canvas(window,width=140,height=34,bg=window.cget("bg"),highlightthickness=0)
smeter_canvas.grid(column=4,row=1,columnspan=2,padx=2)

# Memory buttons
memory_buttons = []
for idx, (freq, mode) in enumerate(FIXED_MEMORIES):
    row_number = 2 + (idx // 6)
    column_number = idx % 6
    pad_left = 14 if column_number == 0 else 3
    color = MODE_COLOR.get(mode, "white")
    if idx >= 12:
        color = "lightgrey"
    btn = Button(window, text=f"{freq}", bg=color, command=lambda f=freq, m=mode: set_memory(f, m), width=9, relief="flat", highlightthickness=0, bd=2)
    btn.grid(column=column_number, row=row_number, pady=4, padx=(pad_left, 5))
    memory_buttons.append(btn)

# Extra memories
group = EXTRA_MEMORIES
if group:
    var = StringVar(value="EXTRA MEMORIES")

    def handler(selection):
        for freq, mode in group:
            if selection == f"  {freq:>6} | {mode:<3}  ":
                set_memory(freq, mode)
                break
        var.set("EXTRA MEMORIES")

    menu = OptionMenu(window, var, " EXTRA MEMORIES ")
    menu.config(width=16, bg="lightgrey", activebackground="lightgrey", font=("Consolas",10), relief="flat", highlightthickness=0, bd=0)

    dropdown = menu["menu"]
    dropdown.delete(0, "end")
    dropdown.config(bg="#202020", fg="white", activebackground="lightgrey", activeforeground="black", font=("Consolas",10), borderwidth=0, tearoff=0)

    dropdown.add_command(label=" ", state="disabled")
    for freq, mode in group:
        text = f"  {freq:>6} | {mode:<3}  "
        color = MODE_COLOR.get(mode.upper(), "black")
        dropdown.add_command(label=text, foreground=color, activeforeground=color, activebackground="grey", command=lambda t=text: handler(t))
    dropdown.add_command(label=" ", state="disabled")

    menu.grid(row=2, column=4, columnspan=2, padx=(4,2))

cw_button1 = Button(window, text=f"{CALLSIGN}", command=lambda: send_cw_message(CALLSIGN), width=11,relief="flat", highlightthickness=0, bd=2)
cw_button1.grid(column=6, row=1, pady=4, padx=(24, 0))
cw_button2 = Button(window, text=f"{LITERAL_1}", command=lambda: send_cw_message(MESSAGE_1), width=11,relief="flat", highlightthickness=0, bd=2)
cw_button2.grid(column=6, row=2, pady=4, padx=(24, 0))
cw_button3 = Button(window, text=f"{LITERAL_2}", command=lambda: send_cw_message(MESSAGE_2), width=11,relief="flat", highlightthickness=0, bd=2)
cw_button3.grid(column=6, row=3, pady=4, padx=(24, 0))
cw_button4 = Button(window, text=f"CQ", command=lambda: send_cw_message(CQ), width=11,relief="flat", highlightthickness=0, bd=2)
cw_button4.grid(column=6, row=4, pady=4, padx=(24, 0))
cw_buttons = [cw_button1, cw_button2, cw_button3, cw_button4]

ToolTip(cw_button1, lambda: CALLSIGN)
ToolTip(cw_button2, lambda: MESSAGE_1)
ToolTip(cw_button3, lambda: MESSAGE_2)
ToolTip(cw_button4, lambda: CQ)

CW_PLACEHOLDER = "Type here you cw message [enter]"
custom_cw_entry = Entry(window,font=('Arial',14),bg="lightgreen",fg="grey",disabledbackground="lightgrey",disabledforeground="grey",relief="flat", highlightthickness=0, bd=0)
custom_cw_entry.insert(0, " " + CW_PLACEHOLDER)
custom_cw_entry.grid(column=0, row=3, columnspan=6, padx=(14,0), pady=2, sticky="we")
custom_cw_entry.bind("<FocusIn>", clear_placeholder)
custom_cw_entry.bind("<FocusOut>", add_placeholder)
custom_cw_entry.bind("<Return>",lambda event: send_custom_cw())

rbn_label = Text(window,height=1, width=30, font=("Arial", 11, "bold"),bd=0,highlightthickness=0,bg=window.cget("bg"))
rbn_label.grid(row=4, column=0, columnspan=6, sticky="w", padx=12, pady=(5, 0))
rbn_label.insert("end", "RBN Spots ")
rbn_label.insert("end", CALLSIGN, "callsign")
rbn_label.config(state="disabled")
                 
rbn_frame = Frame(window)
rbn_frame.grid(row=6, column=0, columnspan=7, sticky="nsew", padx=(12, 0), pady=5)
scrollbar = Scrollbar(rbn_frame)
scrollbar.pack(side=RIGHT, fill=Y)

rbn_list = Listbox(rbn_frame, bg="lightgrey", fg="black", height=5, font=("Consolas", 11), yscrollcommand=scrollbar.set,relief="flat", highlightthickness=0, bd=2)
rbn_list.pack(side=LEFT, fill=BOTH, expand=True)
scrollbar.config(command=rbn_list.yview)

spacer = Frame(window, height=20, bg=window.cget("bg"))
spacer.grid(row=7, column=0, columnspan=6)

dx_label=Text(window,height=1,width=70,font=("Arial",11,"bold"),fg="white",bd=0,highlightthickness=0,bg=window.cget("bg"))
dx_label.grid(row=8,column=0,columnspan=7,sticky="w",padx=12,pady=(5,0))

dx_label.insert("end","DX Cluster : ")
dx_label.insert("end"," connectng ","host")

dx_label.tag_config("host",foreground="red")
dx_label.config(state="disabled")

dx_frame=Frame(window)
dx_frame.grid(row=9,column=0,columnspan=7,sticky="nsew",padx=(12,0),pady=5)
dx_scrollbar=Scrollbar(dx_frame)
dx_scrollbar.pack(side=RIGHT,fill=Y)

dx_list=Listbox(dx_frame,height=10, bg="lightgrey", font=("Consolas",11),yscrollcommand=dx_scrollbar.set,activestyle="none",selectmode=SINGLE,exportselection=False,selectbackground="grey",relief="flat", highlightthickness=0, bd=2)
dx_list.pack(side=LEFT,fill=BOTH,expand=True)
dx_scrollbar.config(command=dx_list.yview)
dx_list.bind("<Double-Button-1>",tune_dxcluster_spot)
dx_list.bind("<Button-3>", search_qrz)

spacer = Frame(window, height=20, bg=window.cget("bg"))
spacer.grid(row=10, column=0, columnspan=6)

spot_label=Text(window,height=1,width=70,font=("Arial",11,"bold"),fg="white",bd=0,highlightthickness=0,bg=window.cget("bg"))
spot_label.grid(row=11,column=0,columnspan=7,sticky="w",padx=12,pady=(5,0))
spot_label.insert("end","SOTA","sota")
spot_label.insert("end"," + ")
spot_label.insert("end","POTA","pota")
spot_label.insert("end"," + ")
spot_label.insert("end","WWFF","wwff")
spot_label.insert("end"," - ")
spot_label.insert("end", SPOT_BANDS, "spot bands")
spot_label.insert("end"," | ")
spot_label.insert("end", SPOT_MODES, "spot modes")
spot_label.insert("end"," | ")
spot_label.insert("end", SPOT_MAX_AGE, "age")
spot_label.insert("end"," min | ")
if SPOT_EUROPE == True:
    spot_label.insert("end"," Europe only")
else:
    spot_label.insert("end"," World Wide")
spot_label.tag_config("sota",foreground="grey")
spot_label.tag_config("pota",foreground="grey")
spot_label.tag_config("wwff",foreground="grey")
spot_label.config(state="disabled")

spot_frame=Frame(window)
spot_frame.grid(row=12,column=0,columnspan=7,sticky="nsew",padx=(12,0),pady=5)
spot_scrollbar=Scrollbar(spot_frame)
spot_scrollbar.pack(side=RIGHT,fill=Y)

spot_list=Listbox(spot_frame,bg="lightgrey", height=12,font=("Consolas",11),yscrollcommand=spot_scrollbar.set,activestyle="none",selectmode=SINGLE,exportselection=False,selectbackground="grey",relief="flat", highlightthickness=0, bd=2)
spot_list.pack(side=LEFT,fill=BOTH,expand=True)
spot_scrollbar.config(command=spot_list.yview)
spot_list.bind("<Double-Button-1>",tune_spot)
spot_list.bind("<Button-3>", search_qrz)

log_button = Button(window,bg="lightgrey", textvariable=log_button_text,command=log_tuned_qso,width=22,relief="flat", highlightthickness=0, bd=2)
log_button.grid(row=13,column=0,columnspan=3,pady=2)

tune_button = Button(window, text="TUNE", width=9, command=toggle_tune,relief="flat", highlightthickness=0, bd=2)
tune_button.grid(row=13, column=6, pady=2, columnspan=1)


# Label left
Label(window,text="RF Gain", bg=window.cget("bg"), fg="yellow").grid(row=13, column=3, padx=(5,5), sticky="e")
# Slider
rf_gain_scale = ttk.Scale(window,from_=45,to=75,orient="horizontal",length=90,command=rf_gain_move)
rf_gain_scale.set(qmx.get_rf_gain())
rf_gain_scale.bind("<ButtonPress-1>", rf_gain_press)
rf_gain_scale.bind("<ButtonRelease-1>", rf_gain_release)
rf_gain_scale.grid(row=13,column=4,padx=2,sticky="w")
# Label value
Label(window, textvariable=rf_gain_display, width=6, bg=window.cget("bg"), fg="yellow").grid(row=13,column=5,padx=2,sticky="w")



update_status()
update_dx_window()
update_spot_window()
update_smeter()
window.after(500, start_dxcluster)
window.after(500, start_rbn)
window.after(500, start_spots)

window.mainloop()