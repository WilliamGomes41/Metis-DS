"""Controlled transport peer; no model knowledge/proposal assumptions."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread, Event
import time
import json


@contextmanager
def peer(*, delay=0, drip=0, code=200, body=b'{"ok":true}', tls_stall=False):
    received = Event()
    stop = Event()
    class Handler(BaseHTTPRequestHandler):
        def handle(self):
            if tls_stall:
                received.set()
                stop.wait(5)
            else:
                super().handle()
        def do_POST(self):
            payload=self.rfile.read(int(self.headers.get('Content-Length',0)))
            received.set()
            stop.wait(delay)
            if stop.is_set():
                return
            response_body=body(json.loads(payload)) if callable(body) else body
            try:
                self.send_response(code)
                self.send_header('Content-Length',str(len(response_body)))
                self.end_headers()
                if drip:
                    for value in response_body:
                        if stop.is_set():break
                        self.wfile.write(bytes([value]));self.wfile.flush()
                        stop.wait(drip)
                else:
                    self.wfile.write(response_body);self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):
                pass
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        yield ('https' if tls_stall else 'http')+'://127.0.0.1:'+str(server.server_port),received
    finally:
        stop.set();server.shutdown();server.server_close();thread.join(2)
