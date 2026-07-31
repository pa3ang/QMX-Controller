import serial
import threading
import time

class QMX:
    MODE = {"LSB":1,"USB":2,"CW":3,"AM":5,"DIGI":6,"TUNE":8}
    BANDS = {
    "LOW":  {"80m":0,"60m":1,"40m":2,"30m":3,"20m":4},
    "MID":  {"60m":0,"40m":1,"30m":2,"20m":3,"17m":4,"15m":5},
    "HIGH": {"20m":0,"17m":1,"15m":2,"12m":3,"11m":4,"10m":5},
    "PLUS": {"160m":0,"80m":1,"60m":2,"40m":3,"30m":4,"20m":5,"17m":6,"15m":7,"12m":8,"11m":9,"10m":10,"6m":11}
    }

    def __init__(self, port, model="PLUS", baudrate=38400):
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.2)
        self.lock = threading.Lock()
        self.model = model.upper()
        self.running = True
        self.tune = False
        self._freq = None
        self._mode = None
        self._vfo = "A"
        self.band = 0
        self.smeter = 0
        self.power = 0.0
        self.tx_hold_until = 0
        self.rf_gain = 54      # default

        threading.Thread(target=self.poll, daemon=True).start()
        threading.Thread(target=self.poll_smeter, daemon=True).start()

    def send(self, cmd):
        with self.lock:
            self.ser.write(cmd.encode())

    def query(self, cmd):
        with self.lock:
            self.ser.write(cmd.encode())
            reply = self.ser.readline().decode(errors="ignore").strip()
        return reply

    def poll(self):
        while self.running:
            if self.tune:
                time.sleep(0.2)
                continue
            try:
                vfo = self.query("FT;")
                self._vfo = "B" if vfo == "FT1;" else "A"
                reply = self.query("FB;" if self._vfo == "B" else "FA;")
                if reply.startswith(("FA","FB")):
                    try:
                        self._freq = int(reply[2:-1])
                    except:
                        pass
                reply = self.query("MD;")
                if reply.startswith("MD"):
                    try:
                        self._mode = int(reply[2:-1])
                    except:
                        pass
                reply = self.query("BN;")
                if reply.startswith("BN"):
                    try:
                        self.band = int(reply[2:-1])
                    except:
                        pass
                reply = self.query("RG;")
                if reply.startswith("RG"):
                    try:
                        self.rf_gain = int(reply[2:-1])
                    except:
                        pass
            except Exception as e:
                print("Poll error:", e)
            time.sleep(0.4)

    def poll_smeter(self):
        while self.running:
            try:
                reply = self.query("TQ;")
                if reply.startswith("TQ"):
                    if reply == "TQ1;":
                        self.tx_hold_until = time.time() + 3.0
                # alleen hier bepalen
                tx = time.time() < self.tx_hold_until
                if tx:
                    reply = self.query("PC;")
                    if reply.startswith("PC"):
                        self.power = int(reply[2:-1]) / 10
                else:
                    reply = self.query("SM;")
                    if reply.startswith("SM"):
                        self.smeter = int(reply[2:-1])

            except Exception as e:
                print("Meter error:", e)

            time.sleep(0.2)

    def set_freq(self, freq):
        cmd = "FB" if self._vfo == "B" else "FA"
        self.send(f"{cmd}{int(freq):011d};")

    def get_freq(self):
        return self._freq

    def set_mode(self, mode):
        if isinstance(mode, str):
            mode = self.MODE[mode.upper()]
        self.send(f"MD{mode};")

    def get_mode(self):
        for name, value in self.MODE.items():
            if value == self._mode:
                return name
        return "Unknown"
        
    def set_band(self, band):
        band = band.strip()
        bn = self.BANDS.get(self.model, {}).get(band)
        if bn is not None:
            self.send(f"BN{bn};")

    def get_band(self):
        return self.band
    
    def get_vfo(self):
        return self._vfo

    def get_strength(self):
        return self.smeter

    def is_tx(self):
        return time.time() < self.tx_hold_until
    
    def get_power(self):
        return self.power

    def send_cw_message(self, message):
        for i in range(0, len(message), 22):
            self.send(f"KY {message[i:i+22]};")
            time.sleep(0.3)

    def tune_on(self):
        self.tune = True
        # do not use self.send() to avoid lock issues with the 2 threads and not be able to reach tune_off 
        self.ser.write(b"MD8;")

    def tune_off(self):
        # do not use self.send() to avoid lock issues
        self.ser.write(b"MD0;")
        self.tune = False

    def set_rf_gain(self, gain):
        gain = max(30, min(80, int(gain)))   # begrenzen op 30..80
        self.send(f"RG{gain};")
        self.rf_gain = gain

    def get_rf_gain(self):
        return self.rf_gain

    def close(self):
        self.running = False
        if self.ser.is_open:
            self.ser.close()

    def get_smeter(self):
        db = self.smeter
        if db < 5:
            return 0
        elif db < 10:
            return 1
        elif db < 15:
            return 2
        elif db < 20:
            return 3
        elif db < 25:
            return 4
        elif db < 30:
            return 5
        elif db < 35:
            return 6
        elif db < 40:
            return 7
        elif db < 46:
            return 8
        elif db < 53:
            return 9
        elif db < 63:
            return 10      # S9+10
        elif db < 73:
            return 11      # S9+20
        elif db < 83:
            return 12      # S9+30
        else:
            return 13      # S9+40