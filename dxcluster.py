import socket,time

class DXCluster:
    def __init__(self,servers,call=None,filters=None,callback=None,status_callback=None):
        self.servers=servers
        self.call=call
        self.filters=filters or []
        self.callback=callback
        self.status_callback=status_callback
        self.sock=None
        self.running=False
        self.logged_in=False
        self.filters_sent=False

    def set_connected(self,connected):
        host=self.host if connected else "offline"
        if self.status_callback:
            self.status_callback(connected,host,self.port)

    def connect(self):
        while True:
            for host,port in self.servers:
                try:
                    self.host=host
                    self.port=port
                    self.status(f"Connecting {host}:{port}")

                    self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    self.sock.settimeout(10)
                    self.sock.connect((host,port))
                    self.sock.settimeout(None)

                    self.set_connected(True)
                    #self.status(f"Connected {host}:{port}")

                    self.running=True 
                    self.logged_in=False
                    self.filters_sent=False
                    self.read_thread()

                except Exception as e:
                    self.status(f"{host}:{port} failed: {e}")

                finally:
                    self.running=False
                    self.set_connected(False)

                    try:
                        if self.sock:self.sock.close()
                    except:
                        pass

            self.status("No DXCluster available, retry in 60 seconds")
            time.sleep(60)

    def status(self,text):
        if self.callback:self.callback(f"~~~ {text}")

    def send(self,text):
        try:self.sock.sendall((text+"\r\n").encode())
        except Exception as e:
            self.status(f"DXCluster send error: {e}")

    def send_filters(self):
        if self.filters_sent:
            return
        for cmd in self.filters:
            cmd=cmd.strip()
            if not cmd:
                continue
            self.send(cmd)
            time.sleep(1)
        self.filters_sent=True

    def login_detected(self,line):
        line=line.lower()
        return "welcome" in line or "logged in" in line or "hello" in line or "dxcluster" in line

    def read_thread(self):
        buffer=""
        while self.running:
            try:
                data=self.sock.recv(4096)
                if not data:
                    self.status("Server closed connection")
                    break
                text=data.decode(errors="ignore")
                if not self.logged_in and "login" in text.lower():
                    self.send(self.call)
                buffer+=text;lines=buffer.split("\n")
                buffer=lines[-1]
                for line in lines[:-1]:
                    line=line.strip().replace("\x07","")
                    if not line:continue
                    print(line)
                    if not self.logged_in and self.login_detected(line):
                        self.logged_in=True
                        self.status(f"Logged in as {self.call}")
                        self.set_connected(True);time.sleep(1)
                        self.send_filters()
                    if self.callback:self.callback(line)
            except Exception as e:
                self.status(f"DXCluster read error: {e}")
                break
        self.running=False
        self.set_connected(False)
        self.status("DXCluster disconnected")

    def close(self):
        self.running=False;self.set_connected(False)
        try:
            if self.sock:self.sock.close()
        except:pass