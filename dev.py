#!/usr/bin/env python3
"""Servidor local para mexer no visual da página, com recarregamento automático.

Uso:
  python dev.py            # abre http://localhost:8000
  python dev.py --port 9000

A cada pedido regenera a página (`python filmes_tv.py --relatorio`, sem pedidos de rede) e, quando
gravas estilo.css, pagina.js ou filmes_tv.py, o browser recarrega sozinho. O aviso de recarregar
só existe aqui: não vai para a página real. Se o código tiver um erro, o erro aparece no browser.
"""
import argparse
import html
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
WATCH = ["filmes_tv.py", "estilo.css", "pagina.js"]
RELOAD = """
<script>
(() => {
  let last = null;
  setInterval(async () => {
    try {
      const t = await (await fetch("/__mtime", { cache: "no-store" })).text();
      if (last !== null && t !== last) location.reload();
      last = t;
    } catch (e) { /* servidor parado: tenta de novo */ }
  }, 700);
})();
</script>
"""
lock = threading.Lock()


def mtime():
    """Última alteração dos ficheiros vigiados (muda sempre que gravas um deles)."""
    return str(max((ROOT / name).stat().st_mtime_ns for name in WATCH))


def inject(page):
    return page + RELOAD


def render():
    """Regenera filmes.html e devolve-o; se falhar, devolve uma página com o erro."""
    with lock:
        r = subprocess.run(
            [sys.executable, "filmes_tv.py", "--relatorio"], cwd=ROOT, capture_output=True, text=True
        )
        if r.returncode != 0:
            erro = html.escape((r.stderr or r.stdout).strip())
            return (
                "<!doctype html><meta charset='utf-8'><title>Erro</title>"
                "<body style='font:15px/1.5 monospace;background:#300;color:#fdd;padding:1.5rem'>"
                f"<h1>Erro ao gerar a página</h1><pre style='white-space:pre-wrap'>{erro}</pre>"
            )
        return (ROOT / "filmes.html").read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body, kind = inject(render()), "text/html; charset=utf-8"
        elif path == "/__mtime":
            body, kind = mtime(), "text/plain"
        else:
            self.send_error(404)
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):   # sem ruído no terminal
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8000)
    port = ap.parse_args().port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"A servir em http://localhost:{port}  (Ctrl+C para parar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
