"""Base comum das verificações no browser (Chromium headless do Playwright).

Estas verificações não fazem parte de `python -m unittest` porque precisam de um browser e do
`filmes.db` local. Cada script compara o que o JavaScript da página faz com um oráculo em Python.
"""
import glob
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import filmes_tv as f  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="filmes-nav-"))


def _chromium():
    achados = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell")))
    if not achados:
        sys.exit("Chromium headless não encontrado em ~/.cache/ms-playwright (instalar o Playwright).")
    return achados[-1]


BROWSER = _chromium()


def abrir_db():
    caminho = ROOT / "filmes.db"
    if not caminho.exists():
        sys.exit("Falta filmes.db: corre `python filmes_tv.py --relatorio`.")
    return sqlite3.connect(caminho)


def gerar(now=None, nome="build.html"):
    """Gera a página para a hora `now` (Lisboa, sem fuso) e devolve (now, html)."""
    now = (now or f.now_lisbon()).replace(microsecond=0)
    antigo = f.OUT_PATH
    f.OUT_PATH = str(TMP / nome)
    try:
        f.report(abrir_db(), now=now)
    finally:
        f.OUT_PATH = antigo
    return now, (TMP / nome).read_text(encoding="utf-8")


def dump(url, orcamento=5000):
    """Abre o endereço, deixa o JavaScript correr e devolve o DOM final."""
    r = subprocess.run([BROWSER, "--no-sandbox", "--disable-gpu", f"--virtual-time-budget={orcamento}", "--dump-dom", url],
                       capture_output=True, text=True, timeout=300)
    return r.stdout


class Resultados:
    def __init__(self):
        self.falhas = []

    def ok(self, nome, cond, detalhe=""):
        print(f"  {'OK       ' if cond else 'FALHOU   '} {nome}" + (f"  [{detalhe}]" if (detalhe and not cond) else ""))
        if not cond:
            self.falhas.append(nome)
        return cond

    def fim(self):
        print("\nTUDO OK" if not self.falhas else f"\n{len(self.falhas)} FALHA(S): {self.falhas}")
        sys.exit(1 if self.falhas else 0)
