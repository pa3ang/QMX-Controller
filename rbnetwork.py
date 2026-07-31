import socket
import threading
import time

class RBNetwork:

    def __init__(self, callsign, host, port, callback=None):
        self.callsign = callsign
        self.host = host
        self.port = port
        self.callback = callback
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._thread, daemon=True).start()

    def _thread(self):
        buffer = ""

        while self.running:
            try:
                s = socket.socket()
                s.connect((self.host, self.port))
                s.sendall((self.callsign + "\n").encode())

                while self.running:
                    data = s.recv(4096).decode(errors="ignore")

                    if not data:
                        break

                    buffer += data
                    lines = buffer.split("\n")
                    buffer = lines[-1]

                    for line in lines[:-1]:
                        self.process(line.strip())

            except Exception as e:
                print("RBN reconnect:", e)
                time.sleep(5)

    def process(self, line):
        line = self.clean(line)

        if self.callsign in line and "CQ" in line:
            formatted = self.format(line)

            if self.callback:
                self.callback(formatted)

    def clean(self, line):
        line = line.replace("\t", " ")
        line = line.replace("-#:", "")
        return " ".join(line.split())

    def format(self, line):
        parts = line.split()

        if len(parts) < 11:
            return line

        spotter = parts[2]
        freq = parts[3]
        dx = parts[4]
        db_val = parts[6]
        wpm = parts[8]
        utc = parts[-1]

        return f"Spotted by: {spotter:<10} {freq:<9} {dx:<9} {db_val:>2} dB {wpm:>3} wpm   {utc}"

    def stop(self):
        self.running = False