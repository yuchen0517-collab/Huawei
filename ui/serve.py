import http.server
import os
import socketserver
import threading
import webbrowser

PORT = int(os.environ.get("PORT", "8000"))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

socketserver.TCPServer.allow_reuse_address = True


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def open_browser():
    webbrowser.open("http://127.0.0.1:%d/" % PORT)


if __name__ == "__main__":
    threading.Timer(0.9, open_browser).start()
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print("Diplomat 已启动: http://127.0.0.1:%d/  (Ctrl+C 停止)" % PORT)
        httpd.serve_forever()