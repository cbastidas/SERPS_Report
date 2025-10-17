from http.client import HTTPSConnection
from base64 import b64encode
from json import loads
from json import dumps

class RestClient:
    domain = "api.dataforseo.com"

    def __init__(self, username: str, password: str, timeout: int = 60):
        self.username = username
        self.password = password
        self.timeout = timeout

    def _headers(self):
        basic = b64encode(f"{self.username}:{self.password}".encode("ascii")).decode("ascii")
        return {
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def request(self, path, method: str = "GET", data=None):
        if not path.startswith("/"):
        
            path = "/" + path

        body = None
        if data is not None:
            body = data if isinstance(data, str) else dumps(data)

        conn = HTTPSConnection(self.domain, timeout=self.timeout)
        try:
            conn.request(method, path, body=body, headers=self._headers())
            resp = conn.getresponse()
            raw = resp.read()

            
            text = raw.decode("utf-8", errors="replace") if raw else ""
            try:
                payload = loads(text) if text else {}
            except Exception:
                payload = {"_raw": text}


            if resp.status < 200 or resp.status >= 300:
                raise RuntimeError(f"HTTP {resp.status} {resp.reason} at {path}: {payload}")

            return payload
        finally:
            conn.close()

    def get(self, path: str):
        return self.request(path, "GET")

    def post(self, path: str, data):
        return self.request(path, "POST", data)
