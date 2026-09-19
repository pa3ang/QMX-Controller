import threading
import requests
import time
import socket
from datetime import datetime,timezone

class SpotBase:
    BAND_LIMITS={"160":(1800000,2000000),"80":(3500000,4000000),"60":(5000000,5500000),"40":(7000000,7300000),"30":(10000000,10200000),"20":(14000000,14350000),"17":(18068000,18168000),"15":(21000000,21450000),"12":(24890000,24990000),"10":(28000000,29700000)}
    EUROPE_PREFIXES=("PA","ON","DL","F","G","GM","GW","EI","I","EA","CT","OZ","SM","LA","OH","SP","OK","OM","OE","HB","S5","9A","YU","LZ","HA","SV","YO","UR","UA")
    def __init__(self,source="SPOT",callback=None,status_callback=None,interval=60,bands=("20","40"),modes=("CW","SSB"),max_age=30,europe=True):
        self.source=source;self.callback=callback;self.status_callback=status_callback;self.interval=interval;self.bands=bands;self.modes=modes;self.max_age=max_age;self.europe=europe;self.running=False;self.thread=None
    def connect(self):
        if self.running:return
        self.running=True;self.status("CONNECTED");self.thread=threading.Thread(target=self._worker,daemon=True);self.thread.start()
    def disconnect(self):
        self.running=False;self.status("DISCONNECTED")
    def status(self,text):
        if self.status_callback:self.status_callback(self.source,text)
    def check_band(self,freq):
        return any(self.BAND_LIMITS[b][0]<=freq<=self.BAND_LIMITS[b][1] for b in self.bands)
    def check_mode(self,mode):
        return not self.modes or mode.upper() in self.modes
    def check_europe(self,call):
        return not self.europe or call.upper().startswith(self.EUROPE_PREFIXES)
    def spot_age(self,value):
        try:
            dt=datetime.fromisoformat(value.replace("Z","+00:00"));dt=dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc);return int((datetime.now(timezone.utc)-dt).total_seconds()/60)
        except:return 999

class POTA(SpotBase):
    def _worker(self):
        while self.running:
            try:
                r=requests.get("https://api.pota.app/spot/activator",timeout=20)
                if r.status_code==200:
                    for s in r.json():
                        age=self.spot_age(s.get("spotTime",""))
                        if age>self.max_age:continue
                        call=s.get("activator","")
                        if not self.check_europe(call):continue
                        freq=float(s.get("frequency",0));freq=freq*1000 if freq<100000 else freq;freq=int(freq)
                        if not self.check_band(freq):continue
                        mode=s.get("mode","").upper()
                        if not self.check_mode(mode):continue
                        self.callback and self.callback({"source":"POTA","call":call,"ref":s.get("reference",""),"freq":freq,"mode":mode,"age":age})
            except Exception as e:
                print("POTA ERROR:",e);self.status("ERROR")
            time.sleep(self.interval)

class SOTA(SpotBase):
    HOST="cluster.sota.org.uk";PORT=7300
    def __init__(self,source="SOTA",callback=None,status_callback=None,interval=60,bands=("20","40"),modes=("CW","SSB"),max_age=15,europe=True,callsign=""):
        super().__init__(source=source,callback=callback,status_callback=status_callback,interval=interval,bands=bands,modes=modes,max_age=max_age,europe=europe);self.callsign=callsign;self.sock=None
    def _worker(self):
        while self.running:
            try:
                self.status("CONNECTING");self.sock=socket.create_connection((self.HOST,self.PORT),timeout=20);self.sock.settimeout(5);print(f"SOTA connected to {self.HOST}:{self.PORT}");self.status("CONNECTED");self.sock.sendall((self.callsign+"\r\n").encode());buffer=b""
                while self.running:
                    try:
                        data=self.sock.recv(4096)
                        if not data:raise ConnectionError("SOTA cluster closed connection")
                        buffer+=data
                        while b"\n" in buffer:
                            line,buffer=buffer.split(b"\n",1);line=line.decode("utf-8",errors="ignore").strip()
                            if line.startswith("DX"):self._process_line(line)
                    except socket.timeout:continue
            except Exception as e:
                print("SOTA ERROR:",e);self.status("ERROR")
                if self.running:time.sleep(10)
            finally:
                if self.sock:
                    try:self.sock.close()
                    except:pass
                    self.sock=None
    def get_mode(self,freq):
        cw_ranges=((1800000,1840000),(3500000,3570000),(7000000,7040000),(10100000,10150000),(14000000,14070000),(18068000,18110000),(21000000,21070000),(24890000,24930000),(28000000,28070000))
        for low,high in cw_ranges:
            if low<=freq<=high:return "CW"
        return "SSB"
    def _process_line(self,line):
        try:
            parts=line.split()
            if len(parts)<7:return
            try:freq=int(float(parts[3])*1000)
            except:return
            call=parts[4].upper();ref=parts[5].upper();time_str=parts[6].upper()
            if not time_str.endswith("Z"):return
            try:spot_hour=int(time_str[:2]);spot_minute=int(time_str[2:4])
            except:return
            now=datetime.now(timezone.utc);age=(now.hour*60+now.minute)-(spot_hour*60+spot_minute)
            if age<0:age+=1440
            if age>self.max_age or not self.check_europe(call) or not self.check_band(freq):return
            mode=self.get_mode(freq)
            if not self.check_mode(mode):return
            if self.callback:self.callback({"source":"SOTA","call":call,"ref":ref,"freq":freq,"mode":mode,"age":age})
        except Exception as e:
            print("SOTA PARSE ERROR:",e);print("LINE:",line)

class WWFF(SpotBase):
    def _worker(self):
        while self.running:
            try:
                r=requests.get("https://spots.wwff.co/static/spots.json",timeout=20)
                if r.status_code==200:
                    for s in r.json():
                        try:age=int((datetime.now(timezone.utc)-datetime.fromtimestamp(int(s.get("spot_time",0)),timezone.utc)).total_seconds()/60)
                        except:continue
                        if age>self.max_age:continue
                        call=s.get("activator","")
                        if not self.check_europe(call):continue
                        try:freq=int(float(s.get("frequency_khz",0))*1000)
                        except:continue
                        if not self.check_band(freq):continue
                        mode=s.get("mode","").upper()
                        if not self.check_mode(mode):continue
                        self.callback and self.callback({"source":"WWFF","call":call,"ref":s.get("reference",""),"freq":freq,"mode":mode,"age":age})
            except Exception as e:
                print("WWFF ERROR:",e);self.status("ERROR")
            time.sleep(self.interval)