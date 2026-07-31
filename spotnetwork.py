import threading
import requests
import time
from datetime import datetime, timezone

class SpotBase:
    BAND_LIMITS={"160":(1800000,2000000),"80":(3500000,4000000),"60":(5000000,5500000),"40":(7000000,7300000),"30":(10000000,10200000),"20":(14000000,14350000),"17":(18068000,18168000),"15":(21000000,21450000),"12":(24890000,24990000),"10":(28000000,29700000)}
    EUROPE_PREFIXES=("PA","ON","DL","F","G","GM","GW","EI","I","EA","CT","OZ","SM","LA","OH","SP","OK","OM","OE","HB","S5","9A","YU","LZ","HA","SV","YO","UR","UA")
    def __init__(self,source="SPOT",callback=None,status_callback=None,interval=60,bands=("20","40"),modes=("CW","SSB"),max_age=30,europe=True):
        self.source=source
        self.callback=callback
        self.status_callback=status_callback
        self.interval=interval
        self.bands=bands
        self.modes=modes
        self.max_age=max_age
        self.europe=europe
        self.running=False
        self.thread=None
    def connect(self):
        if self.running:return
        self.running=True
        self.status("CONNECTED")
        self.thread=threading.Thread(target=self._worker,daemon=True)
        self.thread.start()
    def disconnect(self):
        self.running=False
        self.status("DISCONNECTED")
    def status(self,text):
        if self.status_callback:
            self.status_callback(self.source,text)
    def check_band(self,freq):
        return any(self.BAND_LIMITS[b][0]<=freq<=self.BAND_LIMITS[b][1] for b in self.bands)
    def check_mode(self,mode):
        return not self.modes or mode.upper() in self.modes
    def check_europe(self,call):
        return not self.europe or call.upper().startswith(self.EUROPE_PREFIXES)
    def spot_age(self,value):
        try:
            dt=datetime.fromisoformat(value.replace("Z","+00:00"))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            return int((datetime.now(timezone.utc)-dt).total_seconds()/60)
        except:
            return 999

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
                        freq=float(s.get("frequency",0))
                        if freq<100000:freq*=1000
                        freq=int(freq)
                        if not self.check_band(freq):continue
                        mode=s.get("mode","").upper()
                        if not self.check_mode(mode):continue
                        self.callback and self.callback({"source":"POTA","call":call,"ref":s.get("reference",""),"freq":freq,"mode":mode,"age":age})
            except Exception as e:
                print("POTA ERROR:",e)
                self.status("ERROR")
            time.sleep(self.interval)

class SOTA(SpotBase):
    def _worker(self):
        while self.running:
            try:
                r=requests.get("https://api2.sota.org.uk/api/spots/-1/all",timeout=20)
                if r.status_code==200:
                    for s in r.json():
                        age=self.spot_age(s.get("timeStamp",""))
                        if age>self.max_age:continue
                        call=s.get("callsign","")
                        if not self.check_europe(call):continue
                        freq=s.get("frequency","")
                        if not freq:continue
                        try:
                            freq=int(float(freq)*1000000)
                        except:
                            continue
                        if not self.check_band(freq):continue
                        mode=s.get("mode","").upper()
                        if not self.check_mode(mode):continue
                        ref=s.get("associationCode","")+"/"+s.get("summitCode","")
                        self.callback and self.callback({"source":"SOTA","call":call,"ref":ref,"freq":freq,"mode":mode,"age":age})
            except Exception as e:
                print("SOTA ERROR:",e)
                self.status("ERROR")
            time.sleep(self.interval)

class WWFF(SpotBase):
    def _worker(self):
        while self.running:
            try:
                r=requests.get("https://spots.wwff.co/static/spots.json",timeout=20)
                if r.status_code==200:
                    for s in r.json():
                        try:
                            age=int((datetime.now(timezone.utc)-datetime.fromtimestamp(int(s.get("spot_time",0)),timezone.utc)).total_seconds()/60)
                        except:
                            continue
                        if age>self.max_age:continue
                        call=s.get("activator","")
                        if not self.check_europe(call):continue
                        try:
                            freq=int(float(s.get("frequency_khz",0))*1000)
                        except:
                            continue
                        if not self.check_band(freq):continue
                        mode=s.get("mode","").upper()
                        if not self.check_mode(mode):continue
                        self.callback and self.callback({"source":"WWFF","call":call,"ref":s.get("reference",""),"freq":freq,"mode":mode,"age":age})
            except Exception as e:
                print("WWFF ERROR:",e)
                self.status("ERROR")
            time.sleep(self.interval)