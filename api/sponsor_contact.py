from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import urllib.request

# Contract:
# - Method: POST only
# - Body: application/json or x-www-form-urlencoded with fields: name, email, organization (optional), message
# - Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# - Success: 200 {ok: true}
# - Error: 400/500 with {ok:false, error}

class handler(BaseHTTPRequestHandler):
    def _send(self, code:int, body:dict, headers:dict|None=None):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        if headers:
            for k,v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode('utf-8'))

    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            # Basic invocation log to Vercel function logs
            print("[sponsor_contact] POST invoked")
            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if length > 0 else b''
            ctype = (self.headers.get('Content-Type') or '').lower()
            data = {}
            if 'application/json' in ctype and raw:
                data = json.loads(raw.decode('utf-8'))
            elif 'application/x-www-form-urlencoded' in ctype and raw:
                data = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode('utf-8')).items()}
            else:
                # Try query string as fallback
                q = urllib.parse.urlparse(self.path).query
                if q:
                    data = {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}

            name = (data.get('name') or '').strip()
            email = (data.get('email') or '').strip()
            organization = (data.get('organization') or '').strip()
            message = (data.get('message') or '').strip()

            if not name or not email or not message:
                self._send(400, {"ok": False, "error": "Missing required fields"})
                return

            bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            chat_id = os.environ.get('TELEGRAM_CHAT_ID')
            if not bot_token or not chat_id:
                self._send(500, {"ok": False, "error": "Server not configured"})
                return

            # Build Telegram message
            # Include deployment metadata to confirm source is Vercel
            vercel_env = os.environ.get('VERCEL_ENV')  # production | preview | development
            vercel_url = os.environ.get('VERCEL_URL')  # <deployment>.vercel.app
            vercel_region = os.environ.get('VERCEL_REGION')
            host = self.headers.get('host')
            x_vercel_id = self.headers.get('x-vercel-id')

            meta_parts = []
            if vercel_env: meta_parts.append(f"env={vercel_env}")
            if vercel_url: meta_parts.append(f"url={vercel_url}")
            if vercel_region: meta_parts.append(f"region={vercel_region}")
            if host: meta_parts.append(f"host={host}")
            if x_vercel_id: meta_parts.append(f"id={x_vercel_id}")
            meta_line = urllib.parse.quote("; ".join(meta_parts)) if meta_parts else ""

            text = (
                f"New Sponsor/CSR Inquiry:%0A"
                f"Name: {urllib.parse.quote(name)}%0A"
                f"Email: {urllib.parse.quote(email)}%0A"
                f"Organization: {urllib.parse.quote(organization or '-')}%0A"
                f"Message: {urllib.parse.quote(message)}"
            )
            if meta_line:
                text += f"%0A---%0ASource: {meta_line}"
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}"

            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    self._send(502, {"ok": False, "error": f"Upstream error {resp.status}"}, headers={"Access-Control-Allow-Origin": "*"})
                    return

            self._send(200, {"ok": True}, headers={"Access-Control-Allow-Origin": "*"})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)}, headers={"Access-Control-Allow-Origin": "*"})
