#!/usr/bin/env python3
"""Tierlist: comportamento no browser (Chromium headless), com a página real gerada de filmes.db.

Cenários: vista e comutador, vistos como "por classificar", mover, remover, persistência ao recarregar,
valor corrompido, visto sem metadados, outras abas. As tarefas seguintes acrescentam arrasto, edição de tiers,
pesquisa TMDB, exportar/importar e localStorage bloqueado.
Uso: python3 tools/verificar_tierlist.py
"""
import json

from bs4 import BeautifulSoup

from _nav import Resultados, correr, gerar

_, HTML = gerar()
base = BeautifulSoup(HTML, "html.parser")
ids = [li["data-film"] for li in base.select("section#gravar li.film")]
A, B, C = ids[0], ids[1], ids[2]
R = Resultados()
K = "filmes-tv:tierlist"

SNAP = """
const snap = () => ({
  vista: $('.jump').dataset.vista, tvOculto: $('#main-tv').hidden, tierOculto: $('#main-tier').hidden,
  comutador: !$('.views').hidden,
  tiers: $$('#tl-tiers .tl-tier').map((r) => ({ id: r.dataset.tier,
    nome: $('.tl-nome', r) ? $('.tl-nome', r).value : $('.tl-label', r).textContent,
    cor: $('.tl-label', r).style.background, filmes: $$('.tl-card', r).map((c) => c.dataset.film) })),
  livres: $$('#tl-livres .tl-card').map((c) => c.dataset.film),
  vazio: !$('#tl-vazio').hidden, aviso: !$('#tl-aviso').hidden,
  store: localStorage.getItem('filmes-tv:tierlist'),
});
const T = () => window.FilmesTV.tierlist;
"""


def cena(titulo, **kw):
    print(f"\n{titulo}")
    if kw.get("fase2"):
        kw["fase2"] = SNAP + kw["fase2"]   # a fase 2 corre numa função nova, depois de recarregar
    r = correr(HTML, SNAP + kw.pop("cenario"), **kw)
    if not r.get("ok"):
        R.ok(titulo + " (correu)", False, r.get("erro"))
        return None
    return r


# ---- S1: vista e tiers por omissão
r = cena("S1  abrir na vista Tierlist", query="?v=tierlist", cenario="return snap();")
if r:
    s = r["r"]
    R.ok("comutador visível", s["comutador"])
    R.ok("vista Tierlist ativa e grelha escondida", s["vista"] == "tier" and s["tvOculto"] and not s["tierOculto"])
    R.ok("tiers S A B C D", [t["nome"] for t in s["tiers"]] == list("SABCD"), str(s["tiers"]))
    R.ok("nada por classificar", s["livres"] == [] and s["vazio"])

r = cena("S1b  abrir na grelha e alternar", cenario="""
  const a = snap(); await click($('#v-tier')); const b = snap(); await click($('#v-tv')); return { a, b, c: snap() };""")
if r:
    x = r["r"]
    R.ok("começa na grelha", x["a"]["vista"] == "tv" and not x["a"]["tvOculto"] and x["a"]["tierOculto"])
    R.ok("alterna para a tierlist e volta", x["b"]["vista"] == "tier" and x["c"]["vista"] == "tv" and x["c"]["tierOculto"])

# ---- S2: um visto aparece em "por classificar" (clique real no botão de visto)
r = cena("S2  vistos aparecem por classificar", cenario=f"""
  await click($('#gravar li.film[data-film="{A}"] .mark.seen'));
  await click($('#v-tier'));
  return snap();""")
if r:
    R.ok("o visto está em por classificar", r["r"]["livres"] == [A], str(r["r"]["livres"]))
    R.ok("o aviso 'nada por classificar' desaparece", not r["r"]["vazio"])

# ---- S3: mover, remover e persistir
r = cena("S3  mover, remover e persistir", query="?v=tierlist", cenario=f"""
  window.FilmesTV.marcarVisto('{A}', '{B}'); await wait(100);
  const antes = snap();
  T().soltar('{A}', 't2', 0); T().soltar('{B}', 't2', 0); await wait(100);
  const movidos = snap();
  await click($('#tl-tiers .tl-card[data-film="{A}"] .tl-x')); 
  return {{ antes, movidos, removido: snap() }};""", fase2="return snap();")
if r:
    x, p = r["r"], r["fase1"]
    R.ok("dois vistos por classificar", sorted(p["antes"]["livres"]) == sorted([A, B]), str(p["antes"]["livres"]))
    R.ok("mover para o tier A, B à frente", p["movidos"]["tiers"][1]["filmes"] == [B, A], str(p["movidos"]["tiers"][1]))
    R.ok("já não estão por classificar", p["movidos"]["livres"] == [])
    R.ok("✕ devolve a por classificar", p["removido"]["livres"] == [A] and p["removido"]["tiers"][1]["filmes"] == [B], str(p["removido"]))
    R.ok("persistiu ao recarregar", x["tiers"][1]["filmes"] == [B] and x["livres"] == [A], str(x))
    R.ok("guardado em localStorage com versão 1", json.loads(x["store"])["v"] == 1)

# ---- S4: valor corrompido em localStorage (Review Focus 2)
for nome, valor in (("texto solto", "isto não é json"), ("versão errada", '{"v":9}')):
    r = cena(f"S4  localStorage corrompido ({nome})", query="?v=tierlist", pre=f"try {{ localStorage.setItem('{K}', {json.dumps(valor)}); }} catch (e) {{}}",
             cenario="return snap();")
    if r:
        R.ok("abre com os tiers por omissão", [t["nome"] for t in r["r"]["tiers"]] == list("SABCD"))

# ---- S5: visto sem metadados (Review Focus 3)
r = cena("S5  visto que já não está na grelha e sem metadados", query="?v=tierlist",
         pre="try { localStorage.setItem('filmes-tv:marcas', JSON.stringify({v:1,guardados:[],vistos:['tt9999991'],ocultarVistos:false})); } catch (e) {}",
         cenario="return snap();")
if r:
    R.ok("não aparece e não parte nada", r["r"]["livres"] == [] and len(r["r"]["tiers"]) == 5)

# ---- S6: o filme guardado sobrevive a sair da grelha (metadados guardados na tierlist)
fantasma = json.dumps({"v": 1, "tiers": [{"id": "t1", "nome": "S", "cor": "#ff9f43"}], "itens": {"tt9999992": {"tier": "t1", "pos": 0}},
                       "filmes": {"tt9999992": {"titulo": "Filme Antigo", "ano": "1999", "poster": None}}})
r = cena("S6  filme da tierlist que já não está na grelha", query="?v=tierlist",
         pre=f"try {{ localStorage.setItem('{K}', {json.dumps(fantasma)}); }} catch (e) {{}}", cenario="return snap();")
if r:
    R.ok("aparece com o título guardado", r["r"]["tiers"][0]["filmes"] == ["tt9999992"], str(r["r"]["tiers"]))

# ---- S7: outra aba alterou a tierlist (evento storage)
novo = json.dumps({"v": 1, "tiers": [{"id": "t1", "nome": "Top", "cor": "#6fa8ff"}], "itens": {}, "filmes": {}})
r = cena("S7  evento storage", query="?v=tierlist", cenario=f"""
  localStorage.setItem('{K}', {json.dumps(novo)});
  window.dispatchEvent(new StorageEvent('storage', {{ key: '{K}' }})); await wait(150);
  return snap();""")
if r:
    R.ok("repinta com o estado da outra aba", [t["nome"] for t in r["r"]["tiers"]] == ["Top"], str(r["r"]["tiers"]))

R.fim()
