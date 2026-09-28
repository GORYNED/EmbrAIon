"""Single-request loopback fixture for generic mixed-route integration tests."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import TCPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.headers["Authorization"] == "Bearer " + os.environ["EMBRAION_SESSION_TOKEN"]
        model = os.environ["EMBRAION_UPSTREAM_MODEL"].split("/", 1)[1]
        if model == "first":
            result = {"status": "failed", "failure": "rate-limited"}
            status = 429
        else:
            result = {"status": "completed", "correlationId": body["correlationId"], "callId": "call-test",
                      "observedProvider": "example", "observedModel": model, "outputText": "generic answer"}
            status = 200
        encoded = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class LoopbackServer(HTTPServer):
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


server = LoopbackServer(("127.0.0.1", 0), Handler)
print(server.server_port, flush=True)
server.handle_request()
server.server_close()
