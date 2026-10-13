#!/usr/bin/env python3
"""Tira uma captura da página gerada (útil para ver alterações visuais).

Exemplos:
  python tools/capturar.py saida.png                                  # telemóvel (390 px)
  python tools/capturar.py saida.png --largura 1100 --altura 700
  python tools/capturar.py saida.png --q mulheres                     # com uma pesquisa
  python tools/capturar.py saida.png --css "#agora{display:none}"     # esconder partes
  python tools/capturar.py saida.png --marcar 3 --vistos 2 --guardados-modo   # pré-marcar filmes
  python tools/capturar.py saida.png --vista tierlist --tierlist-demo [--editar]   # a tierlist com dados de exemplo
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
ap.add_argument("--vista", choices=["tv", "tierlist"], default="tv", help="vista a mostrar")
ap.add_argument("--tierlist-demo", action="store_true", help="enche a tierlist com os filmes de Para gravar, repartidos pelos tiers")
ap.add_argument("--livres", type=int, default=0, help="com --tierlist-demo: N filmes por classificar")
ap.add_argument("--selecionar", action="store_true", help="toca no primeiro cartão do primeiro tier (mostra o ✕)")
ap.add_argument("--duelos", choices=["menu", "duelo", "ordem", "conflito"], help="abre o ecrã de duelos (com --tierlist-demo): menu, um duelo, a ordem sugerida, ou a ordem com contradições")
ap.add_argument("--editar", action="store_true", help="abre a tierlist em modo de edição")
a = ap.parse_args()

now, html = gerar()
ids = [li["data-film"] for li in BeautifulSoup(html, "html.parser").select("section#gravar li.film")]
marcas = {"v": 1, "guardados": ids[:a.marcar] + [f"tt000000{i}" for i in range(a.fantasmas)],
          "vistos": ids[a.marcar:a.marcar + a.vistos], "ocultarVistos": a.ocultar}
pre = f"try {{ localStorage.setItem('filmes-tv:marcas', {json.dumps(json.dumps(marcas))}); }} catch (e) {{}}"
depois = "<script>setTimeout(() => document.getElementById('f-guardados').click(), 200);</script>" if a.guardados_modo else ""
if a.tierlist_demo:
    sopa = BeautifulSoup(html, "html.parser")
    def meta(i, n):
        li = sopa.select_one(f"li.film[data-film='{i}']")
        img = li.select_one(".poster img") if li else None
        y = li.select_one("h3 .y") if li else None
        return {"titulo": li.select_one("h3 a").get_text() if li else f"Filme {n}", "ano": y.get_text().strip("() ") if y else None,
                "poster": img["src"] if img else None}
    filmes = {i: meta(i, n) for n, i in enumerate(ids[:a.livres + 22])}
    tiers = [{"id": f"t{k}", "nome": nome, "cor": cor} for k, (nome, cor) in enumerate(
        zip(["10", "9", "8", "7", "6"], ["#b8e65a", "#8ff0cf", "#5ee0e0", "#6fa8ff", "#b48cff"]), 1)]
    itens = {i: {"tier": f"t{1 + n % 5}", "pos": n // 5} for n, i in enumerate(ids[:22])}
    for i in ids[22:22 + a.livres]:   # filmes por classificar (explícitos, sem tier)
        itens[i] = {"tier": None, "pos": len(itens)}
    pre += f"try {{ localStorage.setItem('filmes-tv:tierlist', {json.dumps(json.dumps({'v': 1, 'tiers': tiers, 'itens': itens, 'filmes': filmes}))}); }} catch (e) {{}}"
if a.selecionar:
    depois += "<script>setTimeout(() => document.querySelector('#tl-tiers .tl-card').click(), 300);</script>"
if a.duelos:
    passos = {"menu": 0, "duelo": 1, "ordem": 2, "conflito": 3}[a.duelos]
    depois += """<script>setTimeout(async () => {
      const w = (ms) => new Promise((r) => setTimeout(r, ms)), $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
      $('#tl-duelos').click(); await w(150);
      if (%d >= 1) { $('#tl-duelos-corpo .tl-dl-tier[data-tier="t4"]').click(); await w(150); }
      if (%d >= 2) { let i = 0; while ($$('#tl-duelos-corpo .tl-dl-card').length === 2 && i < 80) {
        const [a, b] = $$('#tl-duelos-corpo .tl-dl-card').map((c) => c.dataset.film); const n = i++;
        const ganha = (%d === 3 && n %% 4 === 3) ? (a < b ? b : a) : (a < b ? a : b);   // no modo conflito inverte alguns duelos
        $('#tl-duelos-corpo .tl-dl-card[data-film="' + ganha + '"]').click(); await w(30); } }
    }, 300);</script>""" % (passos, passos, passos)
if a.editar:
    depois += "<script>setTimeout(() => document.getElementById('tl-editar').click(), 200);</script>"
html = html.replace("<meta charset='utf-8'>", f"<meta charset='utf-8'><script>{pre}</script>", 1)
html = html.replace("</style>", a.css + "</style>", 1) + depois
(TMP / "captura.html").write_text(html, encoding="utf-8")
url = f"file://{TMP / 'captura.html'}?t={f.epoch(now) * 1000}" + (f"&q={quote(a.q)}" if a.q else "") + ("&v=tierlist" if a.vista == "tierlist" else "")
subprocess.run([BROWSER, "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=9000",
                f"--screenshot={a.saida}", f"--window-size={a.largura},{a.altura}", url], capture_output=True)
print("captura:", a.saida)
