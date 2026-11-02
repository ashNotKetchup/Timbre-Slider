"""Tiny stdlib HTTP server for the testbed UI (no extra dependencies)."""
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


STATIC = Path(__file__).resolve().parent / 'static'


def make_server(tb, state, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console for training logs
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path):
            if not path.is_file():
                return self._json({'error': 'not found'}, 404)
            data = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            p = url.path
            if p in ('/', '/index.html'):
                return self._file(STATIC / 'index.html')
            if p == '/api/status':
                return self._json({'stage': state.stage, 'message': state.message, 'error': state.error,
                                   'epoch': state.epoch, 'epochs': state.epochs, 'info': state.info,
                                   'ready': state.stage == 'ready', 'messages': state.messages[-20:]})
            if p == '/api/losses':
                since = int(parse_qs(url.query).get('since', ['0'])[0])
                h = state.history
                cut = lambda xs: xs[since:]  # noqa: E731
                if since > len(h['epoch']):  # history was replaced (e.g. final numbers from train_vae)
                    since = 0
                return self._json({'since': since, 'count': len(h['epoch']), 'epoch': cut(h['epoch']),
                                   'loss': {k: cut(v) for k, v in h['loss'].items()},
                                   'weights': {k: cut(v) for k, v in h['weights'].items()}})
            if p == '/api/sample':
                return self._json(state.sample)
            if p.startswith('/audio/'):
                name = Path(p).name  # no directory traversal
                return self._file(tb.audio_dir / name)
            return self._json({'error': 'not found'}, 404)

        def do_POST(self):
            p = urlparse(self.path).path
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
            if p == '/api/stop':
                state.stop_requested = True
                return self._json({'ok': True})
            if p == '/api/shutdown':  # a newer testbed run is taking over this port
                self._json({'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if p == '/api/decode':
                if state.stage != 'ready':
                    return self._json({'error': f'not ready ({state.stage})'}, 409)
                try:
                    return self._json(tb.decode_edit(body['data']))
                except Exception as e:  # surface errors in the UI
                    return self._json({'error': str(e)}, 500)
            return self._json({'error': 'not found'}, 404)

    last_err = None
    for p in range(port, port + 20):
        try:
            return ThreadingHTTPServer(('127.0.0.1', p), Handler), p
        except OSError as e:
            last_err = e
    raise last_err
