#!/usr/bin/env python3
"""Arrasto com o DEDO na tierlist, com gestos de toque reais (CDP, ver tools/_toque.mjs).

Dois gestos num ecrã de telemóvel emulado (390x844, toque ligado, página com scroll):
  1. press longo num cartão e arrastar para outro tier: o filme tem de mudar de tier e a página não pode rolar;
  2. deslizar logo o dedo na vertical sobre um cartão: a página tem de rolar (o scroll natural não pode ser roubado).
Precisa de `node` (22+) e do Chromium do Playwright. Uso: python3 tools/verificar_toque.py
"""
import json
import subprocess

from bs4 import BeautifulSoup

from _nav import TMP, ROOT, Resultados, gerar

_, HTML = gerar()
ids = [li["data-film"] for li in BeautifulSoup(HTML, "html.parser").select("section#gravar li.film")]
A, B = ids[0], ids[1]
caminho = TMP / "toque.html"
caminho.write_text(HTML, encoding="utf-8")

r = subprocess.run(["node", str(ROOT / "tools/_toque.mjs"), str(caminho), A, B], capture_output=True, text=True, timeout=120)
if r.returncode != 0 or not r.stdout.strip():
    raise SystemExit(f"o gesto não correu: {r.stderr[-400:]}")
x = json.loads(r.stdout.strip().splitlines()[-1])
R = Resultados()

print("\nT1  press longo e arrastar com o dedo")
a = x["arrasto"]
R.ok("o filme mudou para o tier de destino, à frente", a["t1"][A]["tier"] == "t1" and a["t1"][A]["pos"] == 0, str(a["t1"]))
R.ok("a página não rolou durante o arrasto", a["scroll"] == 0, f"scrollY={a['scroll']}")

print("\nT2  deslizar na vertical sobre um cartão faz scroll")
s = x["rolagem"]
R.ok("a página rolou", s["scroll"] > 40, f"scrollY={s['scroll']} (documento {s['doc']})")
R.fim()
