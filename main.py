#!/usr/bin/env python3
# 
# # PA3ANG V1.0  July 2026
# Made on Windows (the Tkinter GUI script is platform independent) but can be used on all operating systems.
#
# The original idea of this program dates back to April 2025 and was developed to support the Radio-Kits Explorer 20 meter transceiver.
# Later it was adapted for the QRP-Labs QMX and QMX+ transceivers, as they use the same CAT protocol based on the Kenwood TS-480.
#
# During development, the program evolved into a much more sophisticated Python application with several class modules and an .ini file
# to customize user settings.
#
# The main functionality is frequency and mode control.
# Additional features include an RBN report window showing your own CQ spots and a DXCluster  and POTA, SOTA, WWF spots window 
# displaying spots within the supported frequency range of the connected QMX model.
#
# The program contains 5 predefined memory buttons and a variable Extra Memories drop-down menu.
#
# For CW operation, four programmable messages are available. One of these is reserved for your callsign and is also used for
# RBN searches and DXCluster login.
# A manual CW message entry is also available through a dedicated input field in the GUI.
#
# The spots in the DXCluster ans Spots window can be double-clicked to tune the QMX and right clicked to bring up qrz.com.
# All 3 list windows are scrollable.
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
#
# PA3ANG V1.1
# Small code improvements and bandplan_lookup(), start_spots(), draw_spacer(), create_listbox()
# edited the above comment lines.
#
# PA3ANG V1.2
# Introduced - + 1 kHz buttons
# Change memory management to 5 QMB memory buttons which can be used also for tempery storage
#   - default values from .ini file and if not 5 existing than rest is empty
#   - right mouse click does memory empty
#   - left mouse click does store and recall
# Changed emory list from drop down to list
#
# PARTLY CHANGED GUI BUTTON SIZE AND FREQUENCY ENTRY FOR LINUX/MINT
#
# PA3ANG V1.3
# Added WebSDR connection with frequency and mode control vice versa
# currently WebSDR Maasbree only!
# 
# PA3ANG V1.4
# Changed SOTA connection from API to Telnet
# Added dynamic choice of websdr  but need to be from WebSDR.org platform
 

import configparser
import threading
import sys
import os
import re
import queue
import webbrowser
import time
from tkinter import *
from tkinter import ttk,IntVar,StringVar
from tkinter import messagebox
from dxcluster import DXCluster
from rbnetwork import RBNetwork
from qmx import QMX
from tooltip import ToolTip
from cloudlog import Cloudlog
from spotnetwork import POTA,SOTA,WWFF
from websdr import WebSDR

window=Tk()
style=ttk.Style()
style.theme_use("clam")

if getattr(sys,'frozen',False):base_path=os.path.dirname(sys.executable)
else:base_path=os.path.dirname(os.path.abspath(__file__))
config=configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.read(os.path.join(base_path,"qmx.ini"))
QMX_MODEL=config.get("QMX","model",fallback="Plus")
qmx=QMX(config['Serial']['port'],model=QMX_MODEL)

websdrs={}
i=1
while True:
    name=config.get("WebSDR",f"websdr{i}_name",fallback="")
    url=config.get("WebSDR",f"websdr{i}_url",fallback="")
    if not name or not url:
        break
    websdrs[name]=url
    i+=1
websdr_sync=False
websdr=None
qmx_ignore_until=0
websdr_ignore_until=0

rf_gain_display=StringVar(value=f"{qmx.get_rf_gain()} dB")

CALLSIGN=config['Messages']['callsign']
MESSAGE_1=config['Messages']['message_1']
LITERAL_1=config['Messages']['literal_1']
MESSAGE_2=config['Messages']['message_2']
LITERAL_2=config['Messages']['literal_2']
CQ=config['Messages']['cq']

QMB=[]
for i in range(1,6):
    value=config["Memories"].get(f"qm{i}","").strip()
    if value:
        freq,mode=value.split(",")
        QMB.append((float(freq)*1000,mode.strip()))
    else:QMB.append(None)

MEMORIES=[]
memory_str=config["Memories"].get("list","")
for item in memory_str.split(";"):
    if item.strip():
        freq,mode=item.split(",")
        MEMORIES.append((float(freq)*1000,mode.strip()))
memory_frame=None

color_str=config['ModeColors']['map']
MODE_COLOR={}
for item in color_str.replace("\n","").split(';'):
    if item.strip():
        key,value=item.split(':')
        MODE_COLOR[key.strip()]=value.strip()

MODES=("LSB","USB","CW","AM","DIGI")

QMX_RANGES={"LOW":(3500,14350),"MID":(5000,21450),"HIGH":(14000,30000),"PLUS":(1800,54000)}
QMX_MIN_FREQ,QMX_MAX_FREQ=QMX_RANGES.get(QMX_MODEL.upper(),QMX_RANGES["MID"])

BANDPLAN=[]
BAND_LIST=[]
for band,value in config["Bandplan"].items():
    band_added=False
    for entry in value.split(";"):
        start,end,mode=entry.split(",")
        start=int(start)
        end=int(end)
        mode=mode.strip().upper()
        BANDPLAN.append((start,end,mode,band.strip()))
        if not band_added and QMX_MIN_FREQ<=start<=QMX_MAX_FREQ:
            BAND_LIST.append(band.strip())
            band_added=True

servers=[]
for line in config.get("DXCluster","servers").splitlines():
    line=line.strip()
    if line:
        host,port=line.split(",")
        servers.append((host,int(port)))
DX_CALL=config["DXCluster"].get("call")
DX_FILTERS=[x.strip() for x in config["DXFilters"]["commands"].splitlines() if x.strip()]

RBN_HOST=config["RBNetwork"].get("host")
RBN_PORT=config["RBNetwork"].getint("port")

all_spots={}
SPOT_BANDS=tuple(x.strip() for x in config["Spots"]["bands"].split(","))
SPOT_MODES=tuple(x.strip().upper() for x in config["Spots"]["modes"].split(","))
SPOT_MAX_AGE=config["Spots"].getint("max_age")
SPOT_EUROPE=config["Spots"].getboolean("europe")

cloudlog=Cloudlog(config.get("Cloudlog","URL"),config.get("Cloudlog","APIKey"),config.get("Cloudlog","StationID"))

window.geometry("670x880")
window.configure(bg="#202020")
window.wm_title(f"QMX Control & Support Program V1.3  ||  QMX Model: {QMX_MODEL}")

last_frequency=0
last_mode="USB"
current_mode=StringVar(value="USB")
dx_queue=queue.Queue()
spot_queue=queue.Queue()
band_var=StringVar(value="BAND")
tune_state=False
log_button_text=StringVar(value="Log QSO with ---")
current_tuned_spot=None
rf_gain_dragging=False

def block_websdr_feedback():
    global websdr_ignore_until
    websdr_ignore_until=time.monotonic()+3.0

def block_qmx_feedback():
    global qmx_ignore_until
    qmx_ignore_until=time.monotonic()+3.0

def serial_read():
    global last_frequency,last_mode
    freq=qmx.get_freq()
    mode=qmx.get_mode()
    frequency_changed=freq and freq!=last_frequency
    mode_changed=mode and mode!=last_mode
    if frequency_changed:
        last_frequency=freq
        entry_frequency.delete(0,END)
        entry_frequency.insert(0,f"{freq/1000:.2f}")
    if mode_changed:
        last_mode=mode
        current_mode.set(mode)
        update_band_menu()
        update_cw_button()
    if websdr_sync and websdr.is_ready() and freq:
        mode_lookup,band=bandplan_lookup(freq/1000)
        sync_mode=mode if mode in ("LSB","USB","CW","AM") else mode_lookup
        websdr_frequency=freq+750 if sync_mode=="CW" else freq
        if time.monotonic()>=qmx_ignore_until and (frequency_changed or mode_changed) and sync_mode and (not websdr.has_band_control or band):
            block_websdr_feedback()
            websdr.tune(band,websdr_frequency,sync_mode)
    bn=qmx.get_band()
    if bn is not None:
        for band,number in qmx.BANDS[qmx.model].items():
            if number==bn:
                band_var.set(band)
                break
    if not rf_gain_dragging:
        gain=qmx.get_rf_gain()
        if int(round(rf_gain_scale.get()))!=gain:
            rf_gain_scale.set(gain)
            rf_gain_display.set(f"{gain} dB")

def set_direct_frequency():
    try:
        freq_khz=float(entry_frequency.get())
        freq_hz=int(freq_khz*1000)
        if QMX_MIN_FREQ<=freq_khz<=QMX_MAX_FREQ:set_frequency(freq_hz)
        else:print("Fout: Frequentie buiten bereik.")
    except ValueError:print("Fout: Ongeldige invoer, voer een geldig getal in.")

def set_frequency(frequency):
    qmx.set_freq(int(frequency))
    entry_frequency.delete(0,END)
    entry_frequency.insert(0,f"{frequency/1000:.2f}")

def mouse_frequency_tune(event):
    try:freq_khz=float(entry_frequency.get())
    except ValueError:return "break"
    if event.num==1:freq_khz-=1.0
    elif event.num==3:freq_khz+=1.0
    else:return "break"
    if QMX_MIN_FREQ<=freq_khz<=QMX_MAX_FREQ:set_frequency(int(freq_khz*1000))
    return "break"

def set_mode(selected_mode):qmx.set_mode(selected_mode)

def set_memory(frequency,mode):
    set_frequency(frequency*1000)
    set_mode(mode)

def show_memories():
    global memory_frame
    if memory_frame is not None:
        memory_frame.destroy()
        memory_frame=None
        return
    memory_frame=Frame(window,bg=window.cget("bg"),bd=1,relief="solid")
    memory_frame.place(x=410,y=80)
    for i,(freq,mode) in enumerate(MEMORIES):
        color=MODE_COLOR.get(mode.upper(),"lightgrey")
        Button(memory_frame,text=f"{freq/1000:.0f} | {mode}",width=16,bg=color,relief="flat",highlightthickness=0,bd=2,command=lambda f=freq/1000,m=mode:select_memory(f,m)).grid(row=i,column=0,padx=2,pady=1)
    memory_frame.bind("<FocusOut>",close_memories)
    memory_frame.focus_set()

def close_memories(event=None):
    global memory_frame
    if memory_frame is None:return
    if event:
        widget=event.widget
        if widget==memory_frame or str(widget).startswith(str(memory_frame)):return
    memory_frame.destroy()
    memory_frame=None

def select_memory(freq,mode):
    set_memory(freq,mode)
    close_memories()

def update_QMB_buttons():
    for i,btn in enumerate(QMB_buttons):
        mem=QMB[i]
        if mem is None:btn.config(text="Empty",bg="lightblue")
        else:
            freq,mode=mem
            color=MODE_COLOR.get(mode.upper(),"lightgrey")
            btn.config(text=f"{freq/1000:.0f} | {mode}",bg=color)

def clear_QMB_memory(index):
    QMB[index]=None
    save_QMB_memories()
    update_QMB_buttons()

def QMB_memory(index):
    if QMB[index] is None:
        QMB[index]=(last_frequency,current_mode.get())
        save_QMB_memories()
    else:
        freq,mode=QMB[index]
        set_memory(freq/1000,mode)
    update_QMB_buttons()

def save_QMB_memories():
    for i,mem in enumerate(QMB,1):
        if mem:
            freq,mode=mem
            config["Memories"][f"qm{i}"]=f"{freq/1000:.0f},{mode}"
        else:config["Memories"][f"qm{i}"]=""
    with open(os.path.join(base_path,"qmx.ini"),"w",encoding="utf-8") as f:config.write(f)

def update_cw_button():
    enabled=current_mode.get()=="CW"
    mode_color=MODE_COLOR.get(current_mode.get(),"lightgrey")
    for button in cw_buttons:button.config(bg=mode_color if enabled else "lightgrey",state="normal" if enabled else "disabled")
    if enabled:
        custom_cw_entry.config(bg=mode_color,fg="grey",state="normal")
        rbn_label.config(fg="white")
        rbn_list.config(fg="black")
    else:
        custom_cw_entry.config(bg=mode_color,fg="grey",state="disabled")
        rbn_label.config(fg="grey")
        rbn_list.config(fg="grey")

def send_cw_message(message):qmx.send_cw_message(message)

def send_custom_cw():
    text=custom_cw_entry.get().strip()
    if not text:return
    send_cw_message(text)
    custom_cw_entry.delete(0,END)
    custom_cw_entry.insert(0," ")
    custom_cw_entry.icursor(1)
    custom_cw_entry.focus_set()

def update_band_menu():
    menu=band_dropdown["menu"]
    menu.delete(0,"end")
    for band in BAND_LIST:menu.add_command(label=band,command=lambda b=band:(band_var.set(b),set_band(b)))

def set_band(band):qmx.set_band(band)

def bandplan_lookup(freq):
    for start,end,mode,band in BANDPLAN:
        if start<=freq<=end:return mode,band
    return None,None

def toggle_tune():
    global tune_state
    if tune_state:
        qmx.tune_off()
        tune_button.config(bg="lightgrey")
    else:
        qmx.tune_on()
        tune_button.config(bg="red")
    tune_state=not tune_state

def update_smeter():
    smeter_canvas.delete("all")
    bw,bh,sp=8,12,3
    total=11*(bw+sp)-sp
    start_x=(int(smeter_canvas["width"])-total)//2
    if qmx.is_tx():
        try:power=qmx.get_power()
        except:power=0
        level=min(10,max(0,int(power*2+0.5)))
        labels={0:"0",2:"1",4:"2",6:"3",8:"4",10:"5W"}
    else:
        try:level=qmx.get_smeter()
        except:level=0
        labels={0:"0",2:"3",4:"5",6:"7",8:"9",10:"+20"}
    for i in range(11):
        x=start_x+i*(bw+sp)
        if i<3:color="orange"
        elif i<9:color="green"
        else:color="red"
        if i>=level:color=window.cget("bg")
        smeter_canvas.create_rectangle(x,5,x+bw,3+bh,fill=color,outline="")
    for pos,text in labels.items():
        x=start_x+pos*(bw+sp)+bw/2
        smeter_canvas.create_text(x,24,text=text,fill="white",font=("Consolas",7))
    window.after(100,update_smeter)

def rf_gain_press(event):
    global rf_gain_dragging
    rf_gain_dragging=True

def rf_gain_move(value):
    gain=int(round(float(value)))
    rf_gain_display.set(f"{gain} dB")

def rf_gain_release(event):
    global rf_gain_dragging
    rf_gain_dragging=False
    gain=int(round(rf_gain_scale.get()))
    qmx.set_rf_gain(gain)

def clear_placeholder(event):
    if custom_cw_entry.get()==" "+CW_PLACEHOLDER:
        custom_cw_entry.delete(0,END)
        custom_cw_entry.insert(0," ")
        custom_cw_entry.icursor(1)
        custom_cw_entry.config(fg="black")

def add_placeholder(event):
    if custom_cw_entry.get().strip()=="":
        custom_cw_entry.delete(0,END)
        custom_cw_entry.insert(0," "+CW_PLACEHOLDER)
        custom_cw_entry.config(fg="grey")

def draw_spacer(row):Frame(window,height=20,bg=window["bg"]).grid(row=row,column=0,columnspan=7)

def create_label(parent,row,width=70):
    label=Text(parent,height=1,width=width,font=("Arial",11,"bold"),fg="white",bd=0,highlightthickness=0,bg=parent.cget("bg"))
    label.grid(row=row,column=0,columnspan=7,sticky="w",padx=12,pady=(5,0))
    return label

def create_listbox(parent,row,height,width=None):
    frame=Frame(parent)
    frame.grid(row=row,column=0,columnspan=7,sticky="nsew",padx=(12,0),pady=5)
    scrollbar=Scrollbar(frame)
    scrollbar.pack(side=RIGHT,fill=Y)
    lb=Listbox(frame,bg="lightgrey",fg="black",height=height,font=("Consolas",11),yscrollcommand=scrollbar.set,activestyle="none",selectmode=SINGLE,exportselection=False,selectbackground="grey",relief="flat",highlightthickness=0,bd=2)
    lb.pack(side=LEFT,fill=BOTH,expand=True)
    scrollbar.config(command=lb.yview)
    return lb

def websdr_frequency_changed(frequency):
    global last_frequency
    if not websdr_sync:return
    if time.monotonic()<websdr_ignore_until:return
    if frequency is None:return
    freq_khz=frequency/1000
    if freq_khz<QMX_MIN_FREQ or freq_khz>QMX_MAX_FREQ:
        print(f"WebSDR frequentie buiten QMX bereik: {freq_khz:.2f} kHz")
        return
    if frequency==last_frequency:return
    print(f"WebSDR -> QMX frequentie: {freq_khz:.2f} kHz")
    block_qmx_feedback()
    set_frequency(frequency)
    last_frequency=frequency

def websdr_mode_changed(mode):
    global last_mode
    if not websdr_sync:return
    if time.monotonic()<websdr_ignore_until:return
    if mode is None:return
 
    qmx_mode=str(mode).upper()
    if qmx_mode==last_mode:return
    print(f"WebSDR -> QMX mode: {qmx_mode}")
    block_qmx_feedback()
    set_mode(qmx_mode)
    last_mode=qmx_mode
    current_mode.set(qmx_mode)
    update_band_menu()
    update_cw_button()

def select_websdr(event=None):
    global websdr_sync,websdr
    choice=websdr_choice.get()
    if choice=="WebSDR OFF":
        print("WebSDR stoppen...")
        websdr_sync=False
        if websdr is not None:
            websdr.stop()
            websdr=None
        websdr_dropdown.configure(style="WebSDROff.TCombobox")
        print("WebSDR Sync OFF")
        return
    websdr_url=websdrs.get(choice)
    if not websdr_url:
        return
    print(f"WebSDR starten: {choice}")
    frequency=qmx.get_freq()
    mode=qmx.get_mode()
    if frequency is None or mode is None:
        print("QMX frequentie/mode nog niet beschikbaar")
        websdr_choice.set("WebSDR OFF")
        return
    freq_khz=frequency/1000
    if mode=="DIGI":
        mode="USB"
    url=f"{websdr_url}?tune={freq_khz:.2f}{mode}"
    print(f"WebSDR URL: {url}")
    if websdr is not None:
        websdr.stop()
        websdr=None
    websdr=WebSDR(url,frequency_callback=websdr_frequency_changed,mode_callback=websdr_mode_changed)
    websdr.start()
    websdr_sync=True
    print(f"WebSDR Sync ON: {choice}")

def update_status():
    serial_read()
    window.after(200,update_status)

def start_rbn():
    rbn=RBNetwork(CALLSIGN,host=RBN_HOST,port=RBN_PORT,callback=lambda line:window.after(0,update_rbn,line))
    rbn.start()

def update_rbn(line):
    rbn_list.insert(0," "+line)
    rbn_list.yview_moveto(0)

spot_states={"SOTA":"DISCONNECTED","POTA":"DISCONNECTED","WWFF":"DISCONNECTED"}
spot_networks=[]
def start_spots():
    for cls,name in ((POTA,"POTA"),(SOTA,"SOTA"),(WWFF,"WWFF")):
        args=dict(source=name,callback=lambda s:window.after(0,spot_received,s),status_callback=spot_status,bands=SPOT_BANDS,modes=SPOT_MODES,max_age=SPOT_MAX_AGE,europe=SPOT_EUROPE,interval=60)
        if cls is SOTA:args["callsign"]=CALLSIGN
        network=cls(**args)
        network.connect()
        spot_networks.append(network)

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
    key=f"{spot['source']}:{spot['call']}:{spot['freq']}"
    all_spots[key]=spot

def update_spot_window():
    yview=spot_list.yview()
    spot_list.delete(0,END)
    spot_list.freq={}
    spot_list.spots={}
    spots=list(all_spots.values())
    spots.sort(key=lambda x:x["age"])
    for index,spot in enumerate(spots):
        freq=spot["freq"]/1000
        line=f" {spot['source']:9}{freq:8.2f}    {spot['mode']:8}{spot['call']:16}{spot['ref']:16}{spot['age']:>3} min"
        spot_list.insert(END,line)
        color={"POTA":"black","SOTA":"red","WWFF":"green"}.get(spot["source"],"white")
        spot_list.itemconfig(index,fg=color)
        spot_list.spots[index]=spot
        spot_list.freq[index]=freq
    spot_list.yview_moveto(yview[0])
    window.after(1000,update_spot_window)

def tune_spot(event):
    global current_tuned_spot
    index=spot_list.nearest(event.y)
    if index<0:return
    spot=spot_list.spots.get(index)
    if not spot:return
    freq=spot["freq"]
    freq_khz=freq/1000
    if freq_khz<QMX_MIN_FREQ or freq_khz>QMX_MAX_FREQ:return
    mode,band=bandplan_lookup(freq_khz)
    if mode is None:return
    set_frequency(freq)
    set_mode(mode)
    current_tuned_spot={"spot_ref":spot["source"],"call":spot["call"],"freq":freq,"mode":"SSB" if mode in ("USB","LSB") else spot["mode"],"ref":spot["ref"]}
    log_button_text.set(f"Log QSO met {spot['call']}")

def start_dxcluster():
    cluster=DXCluster(servers=servers,call=DX_CALL,filters=DX_FILTERS,callback=lambda line:window.after(0,dx_spot_received,line),status_callback=dx_status)
    threading.Thread(target=cluster.connect,daemon=True).start()

def dx_status(connected,host,port):
    window.after(0,lambda:update_dx_label(connected,host,port))

def update_dx_label(connected,host,port):
    color="green" if connected else "lightgrey"
    dx_label.config(state="normal")
    dx_label.delete("1.0","end")
    dx_label.insert("end","DX Cluster : ")
    dx_label.insert("end",host,"host")
    dx_label.insert("end"," - ")
    dx_label.insert("end",DX_FILTERS[-1],"filter")
    dx_label.tag_config("host",foreground=color)
    dx_label.config(state="disabled")

def tune_dxcluster_spot(event):
    global current_tuned_spot
    index=dx_list.nearest(event.y)
    if index<0:return
    line=dx_list.get(index)
    freq=dx_list.freq.get(index)
    if not freq:return
    mode,band=bandplan_lookup(freq)
    if mode is None:return
    call=re.search(r"\s\d+\.\d+\s+([A-Z0-9/]+)",line)
    if not call:return
    dx_call=call.group(1)
    set_frequency(int(freq*1000))
    set_mode(mode)
    current_tuned_spot={"spot_ref":"DX Cluster","call":dx_call,"freq":int(freq*1000),"mode":"SSB" if mode in ("USB","LSB") else mode,"ref":""}
    log_button_text.set(f"Log QSO met {dx_call}")

def update_dx_window():
    while not dx_queue.empty():
        display,freq=dx_queue.get()
        dx_list.insert(END,display)
        dx_list.freq=getattr(dx_list,"freq",{})
        dx_list.freq[dx_list.size()-1]=freq
        dx_list.see(END)
    window.after(200,update_dx_window)

def dx_spot_received(line):
    if line.startswith("~~~ "):
        dx_queue.put((line[3:],None))
        return
    if not line.startswith("DX de"):return
    upper=line.upper()
    if "FT8" in upper or "FT4" in upper:return
    match=re.search(r"\s(\d+\.\d+)\s",line)
    if not match:return
    freq_khz=float(match.group(1))
    if freq_khz<QMX_MIN_FREQ or freq_khz>QMX_MAX_FREQ:return
    mode=bandplan_lookup(freq_khz)
    if mode is None:return
    line=line.replace("\x07","")
    line=line.replace("DX de "," ")
    line=line.replace(":","",1)
    dx_queue.put((line,freq_khz))

def search_qrz(event):
    widget=event.widget
    index=widget.nearest(event.y)
    if index<0:return
    call=None
    if widget==dx_list:
        line=widget.get(index)
        m=re.search(r"\s\d+\.\d+\s+([A-Z0-9/]+)",line)
        if m:call=m.group(1)
    elif widget==spot_list:
        spot=widget.spots.get(index)
        if spot:call=spot["call"]
    if call:webbrowser.open(f"https://www.qrz.com/db/{call}")

def log_tuned_qso():
    if current_tuned_spot is None:return
    if not messagebox.askyesno("Log QSO",f"QSO met {current_tuned_spot['call']} in Cloudlog loggen?"):return
    spot=current_tuned_spot
    mode,band=bandplan_lookup(spot["freq"]/1000)
    if band is None:return
    if spot["spot_ref"] in ("SOTA","POTA","WWFF"):rst="559" if mode=="CW" else "55"
    else:rst="599" if mode=="CW" else "59"
    cloudlog.log_qso(call=spot["call"],freq=spot["freq"]/1000,band=band,mode=mode,rst_sent=rst,rst_rcvd=rst,comment="QMX Controller",activity=spot["spot_ref"],reference=spot["ref"])

draw_spacer(0)

freq_frame=Frame(window,bg=window.cget("bg"))
freq_frame.grid(column=0,row=1,columnspan=2,padx=(10,5))
freq_down_button=Button(freq_frame,text="−",width=1,font=("Arial",12),fg="yellow",bg=window.cget("bg"),activeforeground="yellow",activebackground=window.cget("bg"),command=lambda:mouse_frequency_tune(type("Event",(),{"num":1})()),relief="flat",highlightthickness=0,bd=0)
freq_down_button.pack(side=LEFT)
entry_frequency=Entry(freq_frame,width=8,font=("Arial",18),justify="center",bg=window.cget("bg"),fg="yellow",relief="flat",highlightthickness=0,bd=0)
entry_frequency.pack(side=LEFT,padx=2)
entry_frequency.bind("<Return>",lambda event:set_direct_frequency())
freq_up_button=Button(freq_frame,text="+",width=1,font=("Arial",12),fg="yellow",bg=window.cget("bg"),activeforeground="yellow",activebackground=window.cget("bg"),command=lambda:mouse_frequency_tune(type("Event",(),{"num":3})()),relief="flat",highlightthickness=0,bd=0)
freq_up_button.pack(side=RIGHT)

mode_menu=OptionMenu(window,current_mode,*MODES,command=set_mode)
mode_menu.config(bg="lightgrey",activebackground="lightgrey",width=4,font=("Consolas",10),relief="flat",highlightthickness=0,bd=2)
mode_menu["menu"].config(bg="lightgrey",font=("Consolas",10))
mode_menu.grid(column=2,row=1,padx=2)

band_dropdown=OptionMenu(window,band_var,*BAND_LIST,command=set_band)
band_dropdown.config(width=4,bg="lightgrey",activebackground="lightgrey",font=("Consolas",10),relief="flat",highlightthickness=0,bd=2)
band_dropdown["menu"].config(bg="lightgrey",font=("Consolas",10))
band_dropdown.grid(row=1,column=3,padx=2)

smeter_canvas=Canvas(window,width=130,height=34,bg=window.cget("bg"),highlightthickness=0,bd=0)
smeter_canvas.grid(column=4,row=1,columnspan=2,padx=2)

QMB_buttons=[]
for i in range(5):
    btn=Button(window,text="",bg="lightblue",command=lambda i=i:QMB_memory(i),width=7,relief="flat",highlightthickness=0,bd=2)
    btn.bind("<Button-3>",lambda event,i=i:clear_QMB_memory(i))
    btn.grid(row=2,column=i,padx=(14 if i==0 else 2,2),pady=2)
    QMB_buttons.append(btn)

Button(window,text="MEMORIES",width=7,bg="lightblue",command=show_memories,relief="flat",highlightthickness=0,bd=2).grid(row=2,column=5,padx=2,pady=5,sticky="e")

cw_button1=Button(window,text=f"{CALLSIGN}",command=lambda:send_cw_message(CALLSIGN),width=9,relief="flat",highlightthickness=0,bd=2)
cw_button1.grid(column=6,row=1,pady=4,padx=(10,0))
cw_button2=Button(window,text=f"{LITERAL_1}",command=lambda:send_cw_message(MESSAGE_1),width=9,relief="flat",highlightthickness=0,bd=2)
cw_button2.grid(column=6,row=2,pady=4,padx=(10,0))
cw_button3=Button(window,text=f"{LITERAL_2}",command=lambda:send_cw_message(MESSAGE_2),width=9,relief="flat",highlightthickness=0,bd=2)
cw_button3.grid(column=6,row=3,pady=4,padx=(10,0))
cw_button4=Button(window,text="CQ",command=lambda:send_cw_message(CQ),width=9,relief="flat",highlightthickness=0,bd=2)
cw_button4.grid(column=6,row=4,pady=4,padx=(10,0))
cw_buttons=[cw_button1,cw_button2,cw_button3,cw_button4]

ToolTip(cw_button1,lambda:CALLSIGN)
ToolTip(cw_button2,lambda:MESSAGE_1)
ToolTip(cw_button3,lambda:MESSAGE_2)
ToolTip(cw_button4,lambda:CQ)

CW_PLACEHOLDER="Type here you cw message [enter]"
custom_cw_entry=Entry(window,font=('Arial',14),bg="lightgreen",fg="grey",disabledbackground="lightgrey",disabledforeground="grey",relief="flat",highlightthickness=0,bd=0)
custom_cw_entry.insert(0," "+CW_PLACEHOLDER)
custom_cw_entry.grid(column=0,row=3,columnspan=6,padx=(14,0),pady=2,sticky="we")
custom_cw_entry.bind("<FocusIn>",clear_placeholder)
custom_cw_entry.bind("<FocusOut>",add_placeholder)
custom_cw_entry.bind("<Return>",lambda event:send_custom_cw())

rbn_label=create_label(window,4,30)
rbn_label.insert("end","RBN Spots ")
rbn_label.insert("end",CALLSIGN,"callsign")
rbn_label.config(state="disabled")
rbn_list=create_listbox(window,5,5)

draw_spacer(6)
dx_label=create_label(window,7)
dx_label.insert("end","DX Cluster : ")
dx_label.insert("end"," connecting ","host")
dx_label.tag_config("host",foreground="red")
dx_label.config(state="disabled")
dx_list=create_listbox(window,8,10)
dx_list.bind("<Double-Button-1>",tune_dxcluster_spot)
dx_list.bind("<Button-3>",search_qrz)

draw_spacer(9)
spot_label=create_label(window,10)
spot_label.insert("end","SOTA","sota")
spot_label.insert("end"," + ")
spot_label.insert("end","POTA","pota")
spot_label.insert("end"," + ")
spot_label.insert("end","WWFF","wwff")
spot_label.insert("end"," - ")
spot_label.insert("end",SPOT_BANDS,"spot bands")
spot_label.insert("end"," | ")
spot_label.insert("end",SPOT_MODES,"spot modes")
spot_label.insert("end"," | ")
spot_label.insert("end",SPOT_MAX_AGE,"age")
spot_label.insert("end"," min | ")
if SPOT_EUROPE:spot_label.insert("end"," Europe only")
else:spot_label.insert("end"," World Wide")
spot_label.tag_config("sota",foreground="grey")
spot_label.tag_config("pota",foreground="grey")
spot_label.tag_config("wwff",foreground="grey")
spot_label.config(state="disabled")
spot_list=create_listbox(window,11,12)
spot_list.bind("<Double-Button-1>",tune_spot)
spot_list.bind("<Button-3>",search_qrz)

bottom_frame=Frame(window,bg=window.cget("bg"))
bottom_frame.grid(row=12,column=0,columnspan=7,padx=(24,2),pady=4,sticky="ew")

log_button=Button(bottom_frame,bg="lightgrey",textvariable=log_button_text,command=log_tuned_qso,width=22,relief="flat",highlightthickness=0,bd=2)
log_button.pack(side=LEFT,padx=(0,10))
Label(bottom_frame,text="RF Gain",bg=window.cget("bg"),fg="yellow").pack(side=LEFT,padx=2)
rf_gain_scale=ttk.Scale(bottom_frame,from_=45,to=80,orient="horizontal",length=90,command=rf_gain_move)
rf_gain_scale.set(qmx.get_rf_gain())
rf_gain_scale.bind("<ButtonPress-1>",rf_gain_press)
rf_gain_scale.bind("<ButtonRelease-1>",rf_gain_release)
rf_gain_scale.pack(side=LEFT,padx=2)
Label(bottom_frame,textvariable=rf_gain_display,width=6,bg=window.cget("bg"),fg="yellow").pack(side=LEFT,padx=2)
tune_button=Button(bottom_frame,text="TUNE",width=4,command=toggle_tune,relief="flat",highlightthickness=0,bd=2)
tune_button.pack(side=LEFT,padx=(10,10))

websdr_choice=StringVar(value="WebSDR OFF")

websdr_dropdown=ttk.Combobox(
    bottom_frame,
    textvariable=websdr_choice,
    values=list(websdrs.keys())+["WebSDR OFF"],
    state="readonly",
    width=12,
    style="WebSDROff.TCombobox"
)
websdr_dropdown.bind("<<ComboboxSelected>>",select_websdr)
websdr_dropdown.pack(side=LEFT,padx=4)

update_QMB_buttons()
window.bind("<Button-1>",close_memories,add="+")
update_status()
update_dx_window()
update_spot_window()
update_smeter()
window.after(500,start_dxcluster)
window.after(500,start_rbn)
window.after(500,start_spots)
window.mainloop()
