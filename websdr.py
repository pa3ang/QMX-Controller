# PA3ANG WebSDR controller
# Classic WebSDR control via Playwright
# Made with Maasbree WebSDR as example / template
# http://sdr.websdrmaasbree.nl:8901/

import threading
import time
import queue
from playwright.sync_api import sync_playwright

class WebSDR:
    BAND_MAP={"160m":0,"80m":1,"60m":2,"40m":3,"30m":4,"20m":5,"17m":6,"15m":7}
    BAND_INDEX_MAP={value:key for key,value in BAND_MAP.items()}
    VALID_MODES=("LSB","USB","CW","AM")

    def __init__(self,url,frequency_callback=None,mode_callback=None):
        self.url=url
        self.frequency_callback=frequency_callback
        self.mode_callback=mode_callback
        self.running=False
        self.ready=False
        self.tuning=False
        self.thread=None
        self.page=None
        self.last_frequency=None
        self.last_mode=None
        self.current_band=None
        self.has_band_control=True
        self.commands=queue.Queue()

    def start(self):
        if self.running:return
        self.running=True
        self.thread=threading.Thread(target=self._worker,daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running:return
        self.running=False
        self.commands.put(("stop",None))
        if self.thread:self.thread.join(timeout=3)
        self.thread=None
        self.ready=False
        self.page=None
        self.tuning=False
        self.current_band=None

    def is_ready(self):return self.ready
    def is_tuning(self):return self.tuning
    def get_frequency(self):return self.last_frequency
    def get_mode(self):return self.last_mode
    def get_band(self):return self.current_band
    def set_band_control(self,enabled):self.has_band_control=enabled

    def set_frequency(self,frequency_hz):
        if not self.running:return
        self.commands.put(("frequency",frequency_hz))

    def set_mode(self,mode):
        if not self.running:return
        mode=str(mode).upper()
        if mode not in self.VALID_MODES:
            print(f"WebSDR: onbekende mode {mode}");return
        self.commands.put(("mode",mode))

    def set_band(self,band):
        if not self.running:return
        if band not in self.BAND_MAP:
            print(f"WebSDR: onbekende band {band}");return
        self.commands.put(("band",band))

    def tune(self,band,frequency_hz,mode):
        if not self.running:return
        if self.has_band_control and band not in self.BAND_MAP:
            print(f"WebSDR: onbekende band {band}");return
        mode=str(mode).upper()
        if mode not in self.VALID_MODES:
            print(f"WebSDR: onbekende mode {mode}");return
        self.commands.put(("tune",(band,frequency_hz,mode)))
    def _worker(self):
        from pathlib import Path
        import sys
        if getattr(sys,"frozen",False):
            base_path=Path(sys.executable).parent
            chromium_path=base_path/"chromium"/"chrome-win64"/"chrome.exe"
            if not chromium_path.exists():
                print(f"WebSDR fout: Chromium niet gevonden: {chromium_path}")
                return
            browser_executable=str(chromium_path)
        else:
            browser_executable=None
        with sync_playwright() as p:
            if browser_executable:
                browser=p.chromium.launch(executable_path=browser_executable,headless=False)
            else:
                browser=p.chromium.launch(headless=False)
            context=browser.new_context(viewport={"width":1080,"height":680})
            page=context.new_page()
            self.page=page
            try:
                print(f"WebSDR openen: {self.url}")
                page.goto(self.url,wait_until="domcontentloaded")
                self.has_band_control=bool(page.evaluate("()=>typeof setband_new==='function'"))
                print(f"WebSDR band control: {self.has_band_control}")
                time.sleep(.1)
                page.evaluate("""()=>{const header=document.getElementById('headerwebsdr');if(header)header.style.display='none';}""")
                try:
                    audio_started=page.evaluate("""
                        ()=>{
                            const elements=document.querySelectorAll('input,button');
                            for(const el of elements){
                                const text=(el.value||el.innerText||'').trim().toLowerCase();
                                if(text==='audio start'){el.click();return true;}
                            }
                            return false;
                        }
                    """)
                    if audio_started:print("WebSDR: Audio gestart")
                    else:print("WebSDR: Audio start knop niet gevonden")
                except Exception as e:
                    print(f"WebSDR: Audio start fout: {e}")
                self.ready=True
                print("WebSDR klaar")
                while self.running:
                    self._execute_commands()
                    self._poll_websdr()
                    time.sleep(0.25)
            except Exception as e:
                print(f"WebSDR fout: {e}")
            finally:
                self.ready=False
                self.page=None
                self.tuning=False
                self.current_band=None
                try:browser.close()
                except Exception:pass

    def _execute_commands(self):
        while True:
            try:command,args=self.commands.get_nowait()
            except queue.Empty:return
            if command=="stop":return
            if not self.page:continue
            try:
                if command=="frequency":self._set_frequency(args)
                elif command=="mode":self._set_mode(args)
                elif command=="band":self._set_band(args)
                elif command=="tune":self._tune(args[0],args[1],args[2])
            except Exception as e:
                print(f"WebSDR command fout: {e}")

    def _set_frequency(self,frequency_hz):
        frequency_khz=frequency_hz/1000
        print(f"WebSDR frequentie: {frequency_khz:.2f} kHz")
        self.page.evaluate("""(freq)=>{document.forms.freqform.frequency.value=freq.toFixed(2);setfreq(freq);}""",frequency_khz)
        self.last_frequency=frequency_hz

    def _set_mode(self,mode):
        print(f"WebSDR mode: {mode}")
        self.page.evaluate("(new_mode)=>set_mode(new_mode)",mode)
        self.last_mode=mode

    def _set_band(self,band):
        band_index=self.BAND_MAP.get(band)
        if band_index is None:return
        if self.current_band==band:
            print(f"WebSDR band blijft op {band}");return
        print(f"WebSDR band wijzigen: {self.current_band} -> {band}")
        self.page.evaluate("(b)=>setband_new(b)",band_index)
        time.sleep(0.3)
        self.current_band=band
        print(f"WebSDR band: {band}")

    def _tune(self,band,frequency_hz,mode):
        band_index=self.BAND_MAP.get(band) if self.has_band_control else None
        if self.has_band_control and band_index is None:return
        frequency_khz=frequency_hz/1000
        print(f"WebSDR tune: {frequency_khz:.2f} kHz {mode}")
        self.tuning=True
        try:
            if self.has_band_control and self.current_band!=band:
                self.page.evaluate("(b)=>setband_new(b)",band_index)
                time.sleep(0.3)
                self.current_band=band
            self.page.evaluate("(m)=>set_mode(m)",mode)
            self.page.evaluate("""(freq)=>{document.forms.freqform.frequency.value=freq.toFixed(2);setfreq(freq);}""",frequency_khz)
            self.last_frequency=frequency_hz
            self.last_mode=mode
        except Exception as e:
            print(f"WebSDR tune fout: {e}")
        finally:
            self.tuning=False

    def _poll_websdr(self):
        if not self.page or not self.ready:return
        try:
            frequency=self.page.evaluate("""()=>{const e=document.forms.freqform.frequency;return e?parseFloat(e.value):null;}""")
            mode=self.page.evaluate("""()=>typeof mode!=="undefined"?mode:null""")
            band_index=self.page.evaluate("""()=>typeof band!=="undefined"?band:null""")
            actual_band=self.BAND_INDEX_MAP.get(band_index)
            if actual_band is not None:
                if actual_band!=self.current_band:print(f"WebSDR band gedetecteerd: {actual_band}")
                self.current_band=actual_band
            if frequency is None or mode is None:return
            frequency_hz=frequency*1000
            mode=str(mode).upper()
            frequency_changed=frequency_hz!=self.last_frequency
            mode_changed=mode!=self.last_mode
            if not frequency_changed and not mode_changed:return
            if self.tuning:
                self.last_frequency=frequency_hz
                self.last_mode=mode
                return
            if frequency_changed:
                self.last_frequency=frequency_hz
                print(f"WebSDR frequentie gewijzigd: {frequency:.2f} kHz")
                if self.frequency_callback:self.frequency_callback(frequency_hz)
            if mode_changed:
                self.last_mode=mode
                print(f"WebSDR mode gewijzigd: {mode}")
                if self.mode_callback:self.mode_callback(mode)
        except Exception as e:
            print(f"WebSDR poll fout: {e}")