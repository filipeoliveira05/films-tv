#!/usr/bin/env python3
"""Tira uma captura da página gerada (útil para ver alterações visuais).

Exemplos:
  python tools/capturar.py saida.png                                  # telemóvel (390 px)
  python tools/capturar.py saida.png --largura 1100 --altura 700
  python tools/capturar.py saida.png --q mulheres                     # com uma pesquisa
  python tools/capturar.py saida.png --css "#agora{display:none}"     # esconder partes
  python tools/capturar.py saida.png --marcar 3 --vistos 2 --guardados-modo   # pré-marcar filmes
"""
import argparse
import json
import subprocess
from urllib.parse import quote

from bs4 import BeautifulSoup

from _nav import BROWSER, TMP, f, gerar

ap = argparse.ArgumentParser()
ap.add_argument("saida")
ap.add_argument("--largura", type=int, default=390)
ap.add_argument("--altura", type=int, default=800)
ap.add_argument("--q", default="")
ap.add_argument("--css", default="", help="CSS extra, p. ex. para esconder secções")
ap.add_argument("--marcar", type=int, default=0, help="guarda os N primeiros filmes de Para gravar")
ap.add_argument("--vistos", type=int, default=0, help="marca como vistos os N filmes seguintes")
ap.add_argument("--fantasmas", type=int, default=0, help="N guardados que já não estão disponíveis")
ap.add_argument("--ocultar", action="store_true", help="liga 'ocultar vistos'")
ap.add_argument("--guardados-modo", action="store_true", help="abre no filtro Guardados")
a = ap.parse_args()

now, html = gerar()
ids = [li["data-film"] for li in BeautifulSoup(html, "html.parser").select("section#gravar li.film")]
marcas = {"v": 1, "guardados": ids[:a.marcar] + [f"tt000000{i}" for i in range(a.fantasmas)],
          "vistos": ids[a.marcar:a.marcar + a.vistos], "ocultarVistos": a.ocultar}
pre = f"try {{ localStorage.setItem('filmes-tv:marcas', {json.dumps(json.dumps(marcas))}); }} catch (e) {{}}"
depois = "<script>setTimeout(() => document.getElementById('f-guardados').click(), 200);</script>" if a.guardados_modo else ""
html = html.replace("<meta charset='utf-8'>", f"<meta charset='utf-8'><script>{pre}</script>", 1)
html = html.replace("</style>", a.css + "</style>", 1) + depois
(TMP / "captura.html").write_text(html, encoding="utf-8")
url = f"file://{TMP / 'captura.html'}?t={f.epoch(now) * 1000}" + (f"&q={quote(a.q)}" if a.q else "")
subprocess.run([BROWSER, "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=9000",
                f"--screenshot={a.saida}", f"--window-size={a.largura},{a.altura}", url], capture_output=True)
print("captura:", a.saida)
