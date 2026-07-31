import requests
import json
from datetime import datetime, timezone

class Cloudlog:
    def __init__(self, url, api_key, station_profile_id):
        self.url = url.rstrip("/") + "/index.php/api/qso"
        self.api_key = api_key
        self.station_profile_id = station_profile_id
    def log_qso(self, call, freq, band, mode, rst_sent="599", rst_rcvd="599", comment="", activity="", reference=""):
        now = datetime.now(timezone.utc)
        freq = round(freq, 6)
        adif = (
            f"<CALL:{len(call)}>{call}"
            f"<QSO_DATE:8>{now:%Y%m%d}"
            f"<TIME_ON:6>{now:%H%M%S}"
            f"<FREQ:{len(str(freq))}>{freq}"
            f"<BAND:{len(band)}>{band}"
            f"<MODE:{len(mode)}>{mode}"
            f"<RST_SENT:{len(rst_sent)}>{rst_sent}"
            f"<RST_RCVD:{len(rst_rcvd)}>{rst_rcvd}"
            f"<COMMENT:{len(comment)}>{comment}"
        )
        activity = activity.upper()
        if activity == "SOTA":
            adif += f"<SOTA_REF:{len(reference)}>{reference}"
        elif activity == "POTA":
            adif += f"<POTA_REF:{len(reference)}>{reference}"
        elif activity == "WWFF":
            adif += f"<WWFF_REF:{len(reference)}>{reference}"
        adif += "<EOR>"
        data = {
            "key": self.api_key,
            "station_profile_id": self.station_profile_id,
            "type": "adif",
            "string": adif
        }
        try:
            response = requests.post(
                self.url,
                json=data,
                timeout=10
            )
            return response.ok
        except Exception as e:
            print("Cloudlog error:", e)
            return False