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


def correr(html, cenario, pre="", query="", fase2="", nome="cenario.html", orcamento=20000):
    """Injeta `cenario` (corpo de uma função async) na página, corre-a no Chromium e devolve o que devolveu.

    `pre` corre antes de tudo (p. ex. localStorage ou fetch simulado). Com `fase2`, a página recarrega depois
    da fase 1 e corre a fase 2 (para provar que o estado sobrevive). Devolve {"ok", "r", "fase1"} ou {"ok": False, "erro"}.
    """
    import json as _json
    from bs4 import BeautifulSoup

    corpo = f"""<script>
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const click = async (el) => {{ el.click(); await wait(200); }};
(async () => {{
  const out = (o) => {{ document.body.dataset.res = JSON.stringify(o); }};
  try {{
    if ({_json.dumps(bool(fase2))} && sessionStorage.getItem('fase') === '2') {{
      const r = await (async () => {{ {fase2} }})();
      out({{ ok: true, r, fase1: JSON.parse(sessionStorage.getItem('r1') || 'null') }});
    }} else {{
      const r = await (async () => {{ {cenario} }})();
      if ({_json.dumps(bool(fase2))}) {{ sessionStorage.setItem('r1', JSON.stringify(r)); sessionStorage.setItem('fase', '2'); location.reload(); }}
      else out({{ ok: true, r }});
    }}
  }} catch (e) {{ out({{ ok: false, erro: String(e) }}); }}
}})();
</script>"""
    html = html.replace("<meta charset='utf-8'>", "<meta charset='utf-8'><script>" + pre + "</script>", 1) + corpo
    caminho = TMP / nome
    caminho.write_text(html, encoding="utf-8")
    dom = subprocess.run([BROWSER, "--no-sandbox", "--disable-gpu", f"--virtual-time-budget={orcamento}", "--dump-dom",
                          f"file://{caminho}{query}"], capture_output=True, text=True, timeout=240).stdout
    res = BeautifulSoup(dom, "html.parser").body.get("data-res")
    return _json.loads(res) if res else {"ok": False, "erro": "sem resultado (a página não correu o cenário)"}


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
