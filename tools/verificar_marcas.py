#!/usr/bin/env python3
"""Marcas (visto / guardar), filtro Guardados e Ocultar vistos: comportamento no browser.

Cenários: marcar e desmarcar, sincronizar as linhas do mesmo filme, persistir ao recarregar, filtro Guardados
(com pesquisa), nota dos guardados indisponíveis, desguardar dentro do modo, ocultar vistos (preferência
persistente), combinações, marcas depois de a pesquisa reconstruir as linhas, localStorage bloqueado e
sincronização entre separadores (evento storage).
Uso: python tools/verificar_marcas.py
"""
import json
import subprocess

from bs4 import BeautifulSoup

from _nav import BROWSER as B
from _nav import TMP, f, gerar

S = str(TMP)
N0, HTML = gerar()
T = f.epoch(N0) * 1000
base = BeautifulSoup(HTML, "html.parser")
secoes = {sid: [li["data-film"] for li in base.select(f"section#{sid} ol.films > li.film")] for sid in ("agora", "gravar", "vir")}
# um filme em "Para gravar" e em "A vir" (para testar a sincronização entre as duas linhas) e um só em "Para gravar"
ambos = [i for i in secoes["gravar"] if i in secoes["vir"]]
A = ambos[0] if ambos else secoes["gravar"][0]
Bf = [i for i in secoes["gravar"] if i != A][0]
n_li = lambda fid, sec=None: sum(secoes[s].count(fid) for s in (sec or secoes))

LIB = r"""
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const click = async (el) => { el.click(); await wait(250); };
const li = (id, sec) => $$(`#${sec || 'gravar'} li.film[data-film="${id}"]`)[0];
const snap = () => ({
  sec: Object.fromEntries(['agora', 'gravar', 'vir'].map((id) => [id, {
    count: $(`#${id} h2 .count`).textContent,
    ids: $$(`#${id} li.film`).map((x) => x.dataset.film),
    hidden: $(`#${id}`).hidden,
    empty: $(`#${id} .empty`).hidden ? null : $(`#${id} .empty`).textContent }])),
  nav: Object.fromEntries(['agora', 'gravar', 'vir'].map((id) => [id, $(`.jump a[href="#${id}"] b`).textContent])),
  g: { n: $('#f-guardados .n').textContent, p: $('#f-guardados').getAttribute('aria-pressed') },
  v: { n: $('#f-vistos .n').textContent, p: $('#f-vistos').getAttribute('aria-pressed') },
  nota: $('.nota').hidden ? null : $('.nota').textContent,
  details: $('details') ? ($('details').hidden ? 'escondida' : 'visivel') : null,
  store: localStorage.getItem('filmes-tv:marcas'),
  marcasVisiveis: $$('.marks').length > 0 && $$('.marks').every((m) => !m.hidden),
  cls: (id, sec) => { const e = li(id, sec); return e ? { saved: e.classList.contains('is-saved'), seen: e.classList.contains('is-seen'),
      ps: $('.mark.save', e).getAttribute('aria-pressed'), pv: $('.mark.seen', e).getAttribute('aria-pressed') } : null; },
});
const clsAll = (id) => ['gravar', 'vir', 'agora'].flatMap((s) => $$(`#${s} li.film[data-film="${id}"]`).map((e) => ({
  sec: s, saved: e.classList.contains('is-saved'), seen: e.classList.contains('is-seen'),
  ps: $('.mark.save', e).getAttribute('aria-pressed'), pv: $('.mark.seen', e).getAttribute('aria-pressed') })));
const clone = (o) => JSON.parse(JSON.stringify(o, (k, v) => (typeof v === 'function' ? undefined : v)));
const typeQ = async (txt) => { const q = $('#q'); q.value = txt; q.dispatchEvent(new Event('input', { bubbles: true })); await wait(400); };
"""


def run(pre="", fase1="", fase2="", query=""):
    """fase1 corre ao abrir; se houver fase2, a página recarrega e corre a fase2 (o armazenamento tem de sobreviver)."""
    corpo = f"""<script>{LIB}
(async () => {{
  const out = (o) => {{ document.body.dataset.res = JSON.stringify(o); }};
  try {{
    if ({json.dumps(bool(fase2))} && sessionStorage.getItem('fase') === '2') {{
      const r = await (async () => {{ {fase2} }})();
      out({{ ok: true, r, fase1: JSON.parse(sessionStorage.getItem('r1') || 'null') }});
    }} else {{
      const r = await (async () => {{ {fase1} }})();
      if ({json.dumps(bool(fase2))}) {{ sessionStorage.setItem('r1', JSON.stringify(r)); sessionStorage.setItem('fase', '2'); location.reload(); }}
      else out({{ ok: true, r }});
    }}
  }} catch (e) {{ out({{ ok: false, erro: String(e) }}); }}
}})();
</script>"""
    html = HTML.replace("<meta charset='utf-8'>", "<meta charset='utf-8'><script>" + pre + "</script>", 1) + corpo
    open(f"{S}/marcas_run.html", "w", encoding="utf-8").write(html)
    url = f"file://{S}/marcas_run.html?t={T}" + (f"&q={query}" if query else "")
    dom = subprocess.run([B, "--no-sandbox", "--disable-gpu", "--virtual-time-budget=20000", "--dump-dom", url],
                         capture_output=True, text=True, timeout=240).stdout
    res = BeautifulSoup(dom, "html.parser").body.get("data-res")
    return json.loads(res) if res else {"ok": False, "erro": "sem resultado (página não correu o cenário)"}


falhas = []
def verifica(nome, cond, detalhe=""):
    print(f"  {'OK       ' if cond else 'FALHOU   '} {nome}" + (f"  [{detalhe}]" if (detalhe and not cond) else ""))
    if not cond: falhas.append(nome)

def cenario(titulo, r):
    print(f"\n{titulo}")
    if not r.get("ok"):
        print("  ERRO:", r.get("erro")); falhas.append(titulo + " (erro)"); return False
    return True

# ---------------------------------------------------------------- S1: marcar, sincronizar linhas, persistir
r = run(fase1=f"""
  const s0 = clone(snap());
  const antes = clsAll('{A}');
  await click($('.mark.save', li('{A}')));
  await click($('.mark.seen', li('{Bf}')));
  return {{ s0, antes, depois: clone(snap()), a: clsAll('{A}'), b: clsAll('{Bf}'), store: localStorage.getItem('filmes-tv:marcas') }};
""", fase2=f"""
  return {{ s: clone(snap()), a: clsAll('{A}'), b: clsAll('{Bf}') }};
""")
if cenario("S1  marcar e persistir", r):
    x, p = r["fase1"], r["r"]
    verifica("botões visíveis (o script mostra-os)", x["s0"]["marcasVisiveis"])
    verifica("nada marcado ao início", x["s0"]["g"]["n"] == "0" and x["s0"]["v"]["n"] == "0" and all(not c["saved"] and not c["seen"] for c in x["antes"]))
    verifica("guardar: todas as linhas do filme ficam guardadas", len(x["a"]) == n_li(A) and all(c["saved"] and c["ps"] == "true" for c in x["a"]), str(x["a"]))
    verifica("guardar não marca como visto", all(not c["seen"] and c["pv"] == "false" for c in x["a"]))
    verifica("visto: todas as linhas ficam vistas", len(x["b"]) == n_li(Bf) and all(c["seen"] and c["pv"] == "true" for c in x["b"]))
    verifica("botão Guardados mostra 1", x["depois"]["g"]["n"] == "1", x["depois"]["g"])
    verifica("botão Vistos mostra 1", x["depois"]["v"]["n"] == "1", x["depois"]["v"])
    verifica("guardado em localStorage", A in json.loads(x["store"])["guardados"] and Bf in json.loads(x["store"])["vistos"], x["store"])
    verifica("contagens das secções não mudam ao marcar", x["depois"]["nav"] == x["s0"]["nav"])
    verifica("depois de recarregar: guardado persiste", all(c["saved"] for c in p["a"]) and len(p["a"]) == n_li(A), str(p["a"]))
    verifica("depois de recarregar: visto persiste", all(c["seen"] for c in p["b"]) and len(p["b"]) == n_li(Bf))
    verifica("depois de recarregar: botões com a contagem", p["s"]["g"]["n"] == "1" and p["s"]["v"]["n"] == "1")

# ---------------------------------------------------------------- S2: desmarcar
r = run(fase1=f"""
  await click($('.mark.save', li('{A}'))); await click($('.mark.save', li('{A}')));
  await click($('.mark.seen', li('{A}'))); await click($('.mark.seen', li('{A}')));
  return {{ a: clsAll('{A}'), s: clone(snap()) }};
""")
if cenario("S2  desmarcar", r):
    x = r["r"]
    verifica("voltar a tocar desmarca", all(not c["saved"] and not c["seen"] and c["ps"] == "false" and c["pv"] == "false" for c in x["a"]))
    verifica("contagens a 0", x["s"]["g"]["n"] == "0" and x["s"]["v"]["n"] == "0")

# ---------------------------------------------------------------- S3: filtro Guardados + pesquisa + nota
r = run(fase1=f"""
  const s0 = clone(snap());
  await click($('.mark.save', li('{A}')));
  await click($('#f-guardados'));
  const modo = clone(snap());
  await typeQ('zzzzzz'); const pesq = clone(snap());
  await typeQ(''); await click($('#f-guardados'));
  return {{ s0, modo, pesq, fim: clone(snap()) }};
""")
if cenario("S3  filtro Guardados", r):
    x = r["r"]; m = x["modo"]
    verifica("botão fica premido", m["g"]["p"] == "true")
    verifica("só o filme guardado, em todas as suas secções", all(m["sec"][s]["ids"] == ([A] if A in secoes[s] else []) for s in ("gravar", "vir")), str({s: m['sec'][s]['ids'] for s in ('gravar', 'vir')}))
    verifica("contagens das secções e dos atalhos acompanham", all(m["sec"][s]["count"] == str(n_li(A, [s])) and m["nav"][s] == str(n_li(A, [s])) for s in ("gravar", "vir")))
    verifica("A dar agora esconde-se se não houver guardados nela", m["sec"]["agora"]["hidden"] == (A not in secoes["agora"]))
    verifica("'Sem correspondência' escondida neste modo", m["details"] in (None, "escondida"), str(m["details"]))
    verifica("sem nota quando todos os guardados estão disponíveis", m["nota"] is None, str(m["nota"]))
    verifica("pesquisa sem resultados dentro dos guardados", all(x["pesq"]["sec"][s]["ids"] == [] and x["pesq"]["sec"][s]["empty"] == "Nenhum resultado" for s in ("gravar", "vir")))
    verifica("voltar a tocar regressa à lista geral", x["fim"]["g"]["p"] == "false" and x["fim"]["nav"] == x["s0"]["nav"], str(x["fim"]["nav"]))

# ---------------------------------------------------------------- S4: nota dos indisponíveis
CASOS_NOTA = [
    (["tt0000001"], "1 guardado já não está disponível (reaparece se voltar a passar)"),
    (["tt0000001", "tt0000002"], "2 guardados já não estão disponíveis (reaparecem se voltarem a passar)"),
]
for fake, texto in CASOS_NOTA:
    seed = json.dumps({"v": 1, "guardados": [A] + fake, "vistos": [], "ocultarVistos": False})
    r = run(pre=f"try {{ localStorage.setItem('filmes-tv:marcas', {json.dumps(seed)}); }} catch (e) {{}}",
            fase1="const fora = clone(snap()); await click($('#f-guardados')); return { fora, modo: clone(snap()) };")
    if cenario(f"S4  nota com {len(fake)} guardado(s) indisponível(eis)", r):
        x = r["r"]
        verifica("só conta como guardado o que está disponível", x["fora"]["g"]["n"] == "1", x["fora"]["g"])
        verifica("sem nota fora do modo Guardados", x["fora"]["nota"] is None)
        verifica("nota no modo Guardados", x["modo"]["nota"] == texto, str(x["modo"]["nota"]))
        verifica("o que está disponível continua a aparecer", A in x["modo"]["sec"]["gravar"]["ids"] or A in x["modo"]["sec"]["vir"]["ids"])

# ---------------------------------------------------------------- S5: desguardar dentro do modo + mensagem de vazio
r = run(fase1=f"""
  await click($('.mark.save', li('{A}'))); await click($('#f-guardados'));
  await click($('.mark.save', li('{A}')));
  return clone(snap());
""")
if cenario("S5  desguardar dentro do modo Guardados", r):
    x = r["r"]
    verifica("o filme desaparece da lista", all(x["sec"][s]["ids"] == [] for s in ("gravar", "vir")))
    verifica("mensagem de vazio própria do modo", x["sec"]["gravar"]["empty"] == "Nenhum guardado aqui", str(x["sec"]["gravar"]["empty"]))
    verifica("botão Guardados a 0 e ainda premido", x["g"]["n"] == "0" and x["g"]["p"] == "true")

# ---------------------------------------------------------------- S6: ocultar vistos (+ persistência da preferência)
r = run(fase1=f"""
  const s0 = clone(snap());
  await click($('.mark.seen', li('{Bf}')));
  const marcado = clone(snap());
  await click($('#f-vistos'));
  return {{ s0, marcado, oculto: clone(snap()) }};
""", fase2=f"""
  return clone(snap());
""")
if cenario("S6  ocultar vistos", r):
    x, p = r["fase1"], r["r"]
    verifica("sem ocultar, o visto continua na lista (esbatido)", n_li(Bf) == sum(x["marcado"]["sec"][s]["ids"].count(Bf) for s in ("agora", "gravar", "vir")))
    verifica("ocultar: o filme visto sai de todas as secções", all(Bf not in x["oculto"]["sec"][s]["ids"] for s in ("agora", "gravar", "vir")))
    verifica("contagens acompanham", x["oculto"]["sec"]["gravar"]["count"] == str(int(x["s0"]["sec"]["gravar"]["count"]) - n_li(Bf, ["gravar"])), str(x["oculto"]["sec"]["gravar"]["count"]))
    verifica("botão premido e com a contagem de vistos", x["oculto"]["v"]["p"] == "true" and x["oculto"]["v"]["n"] == "1", str(x["oculto"]["v"]))
    verifica("preferência guardada", json.loads(x["oculto"]["store"])["ocultarVistos"] is True)
    verifica("depois de recarregar continua oculto", Bf not in p["sec"]["gravar"]["ids"] and p["v"]["p"] == "true", str(p["v"]))

# ---------------------------------------------------------------- S7: combinação guardado + visto + ocultar
r = run(fase1=f"""
  await click($('.mark.save', li('{A}'))); await click($('.mark.seen', li('{A}')));
  await click($('#f-guardados'));
  const visivel = clone(snap());
  await click($('#f-vistos'));
  return {{ visivel, oculto: clone(snap()) }};
""")
if cenario("S7  guardado e visto, com 'ocultar vistos'", r):
    x = r["r"]
    verifica("um filme guardado e visto aparece nos guardados", A in x["visivel"]["sec"]["gravar"]["ids"] or A in x["visivel"]["sec"]["vir"]["ids"])
    verifica("com 'ocultar vistos' sai também dos guardados", all(x["oculto"]["sec"][s]["ids"] == [] for s in ("gravar", "vir")))

# ---------------------------------------------------------------- S8: marcas sobrevivem à pesquisa (as linhas são reconstruídas)
titulo_A = base.select_one(f"li.film[data-film='{A}'] h3 a").get_text()
r = run(fase1=f"""
  await click($('.mark.save', li('{A}'))); await click($('.mark.seen', li('{A}')));
  await typeQ({json.dumps(titulo_A.split()[0])});
  return {{ a: clsAll('{A}') }};
""")
if cenario("S8  as marcas sobrevivem à pesquisa", r):
    a = r["r"]["a"]
    verifica("linhas reconstruídas mantêm as marcas", len(a) >= 1 and all(c["saved"] and c["seen"] and c["ps"] == "true" and c["pv"] == "true" for c in a), str(a))

# ---------------------------------------------------------------- S9: armazenamento bloqueado
r = run(pre="Storage.prototype.getItem = () => { throw new Error('bloqueado'); }; Storage.prototype.setItem = () => { throw new Error('bloqueado'); };",
        fase1=f"""
  await click($('.mark.save', li('{A}')));
  return {{ a: clsAll('{{A}}'.replace('{{A}}', '{A}')), g: $('#f-guardados .n').textContent }};
""")
if cenario("S9  localStorage bloqueado (modo privado)", r):
    verifica("a marca funciona na sessão, sem erros", all(c["saved"] for c in r["r"]["a"]) and r["r"]["g"] == "1", str(r["r"]))

# ---------------------------------------------------------------- S10: sincronização entre separadores
r = run(fase1=f"""
  localStorage.setItem('filmes-tv:marcas', JSON.stringify({{ v: 1, guardados: [], vistos: ['{A}'], ocultarVistos: false }}));
  window.dispatchEvent(new StorageEvent('storage', {{ key: 'filmes-tv:marcas' }}));
  await wait(300);
  return {{ a: clsAll('{A}'), v: $('#f-vistos .n').textContent }};
""")
if cenario("S10 sincronização entre separadores (evento 'storage')", r):
    verifica("outra aba marcou como visto: esta atualiza", all(c["seen"] for c in r["r"]["a"]) and r["r"]["v"] == "1", str(r["r"]))

print("\nTUDO OK" if not falhas else f"\n{len(falhas)} FALHA(S): {falhas}")
