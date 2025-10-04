from http.server import BaseHTTPRequestHandler
import json
import os


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode('utf-8'))

    def do_POST(self):
        try:
            # Verify Telegram secret token if configured
            expected = os.environ.get('TELEGRAM_WEBHOOK_SECRET')
            got = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if expected and got != expected:
                self._send(401, {"ok": False, "error": "Unauthorized"})
                return

            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if length > 0 else b''
            update = {}
            if raw:
                try:
                    update = json.loads(raw.decode('utf-8'))
                except Exception:
                    update = {}

            # Basic logging of the update for verification in Vercel logs
            print('[telegram_webhook] update:', json.dumps(update, ensure_ascii=False))

            # Always respond 200 quickly to acknowledge receipt
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})
