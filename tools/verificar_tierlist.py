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
    R.ok("tiers 10 9 8 7 6", [t["nome"] for t in s["tiers"]] == ["10", "9", "8", "7", "6"], str(s["tiers"]))
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
        R.ok("abre com os tiers por omissão", [t["nome"] for t in r["r"]["tiers"]] == ["10", "9", "8", "7", "6"])

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

# ---- S8: arrasto a sério (eventos de ponteiro sintéticos sobre o SortableJS)
ARRASTAR = """
const arrastar = async (card, destino, dx = 20, dy = 20) => {
  const r = card.getBoundingClientRect(), d = destino.getBoundingClientRect();
  const ev = (tipo, x, y, alvo) => alvo.dispatchEvent(new PointerEvent(tipo, { bubbles: true, cancelable: true, clientX: x, clientY: y,
    button: 0, buttons: tipo === 'pointerup' ? 0 : 1, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
  const x0 = r.x + r.width / 2, y0 = r.y + r.height / 2, x1 = d.x + dx, y1 = d.y + dy;
  ev('pointerdown', x0, y0, card);
  for (let i = 1; i <= 12; i++) { ev('pointermove', x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * i / 12, document); await wait(60); }
  // o Sortable ignora movimentos para as mesmas coordenadas e durante as animações: mexe-se um pouco dentro do destino
  for (const [dx2, dy2] of [[3, 3], [6, 5], [4, 4]]) { await wait(200); ev('pointermove', x1 + dx2, y1 + dy2, document); }
  await wait(300);
  ev('pointerup', x1 + 4, y1 + 4, document);
  await wait(400);
};
"""
r = cena("S8  arrasto com o SortableJS", query="?v=tierlist", cenario=ARRASTAR + f"""
  window.FilmesTV.marcarVisto('{A}', '{B}'); await wait(100);
  await arrastar($('#tl-livres .tl-card[data-film="{A}"]'), $('#tl-tiers .tl-lista[data-tier="t1"]'));
  const aposA = snap();
  await arrastar($('#tl-livres .tl-card[data-film="{B}"]'), $('#tl-tiers .tl-lista[data-tier="t3"]'));
  const aposB = snap();
  await arrastar($('#tl-tiers .tl-card[data-film="{A}"]'), $('#tl-livres'));
  return {{ aposA, aposB, fim: snap() }};""")
if r:
    x = r["r"]
    R.ok("arrastar de por classificar para o tier S", x["aposA"]["tiers"][0]["filmes"] == [A], str(x["aposA"]["tiers"][0]))
    R.ok("arrastar para outro tier (B)", x["aposB"]["tiers"][2]["filmes"] == [B], str(x["aposB"]["tiers"][2]))
    R.ok("arrastar de volta para por classificar", x["fim"]["livres"] == [A] and x["fim"]["tiers"][0]["filmes"] == [], str(x["fim"]))
    R.ok("o arrasto ficou guardado", json.loads(x["fim"]["store"])["itens"][B]["tier"] == "t3")

# ---- S9: editar tiers
r = cena("S9  editar tiers", query="?v=tierlist", cenario=f"""
  window.FilmesTV.marcarVisto('{A}'); await wait(100);
  T().soltar('{A}', 't2', 0); await wait(100);
  await click($('#tl-editar'));
  const emEdicao = snap();
  const input = $('.tl-tier[data-tier="t1"] .tl-nome');
  input.value = 'Obras-primas'; input.dispatchEvent(new Event('change', {{ bubbles: true }})); await wait(150);
  const nome = snap();
  await click($('.tl-tier[data-tier="t1"] .tl-cores button:nth-child(4)')); 
  const cor = snap();
  await click($('#tl-novo-tier')); const novo = snap();
  T().soltarTier('t3', 0); await wait(100); const ordem = snap();
  await click($('.tl-tier[data-tier="t2"] .tl-del')); const apagado = snap();
  await click($('#tl-editar'));
  return {{ emEdicao, nome, cor, novo, ordem, apagado, fim: snap() }};""",
         fase2="return snap();")
if r:
    x, p = r["r"], r["fase1"]
    R.ok("o modo de edição mostra campos de nome", all(t["nome"] for t in p["emEdicao"]["tiers"]) and len(p["emEdicao"]["tiers"]) == 5)
    R.ok("renomear", p["nome"]["tiers"][0]["nome"] == "Obras-primas", str(p["nome"]["tiers"][0]))
    R.ok("mudar a cor", p["cor"]["tiers"][0]["cor"] != p["nome"]["tiers"][0]["cor"])
    R.ok("+ tier acrescenta uma linha", len(p["novo"]["tiers"]) == 6 and p["novo"]["tiers"][5]["id"] == "t6")
    R.ok("reordenar um tier", [t["id"] for t in p["ordem"]["tiers"]][0] == "t3", str([t["id"] for t in p["ordem"]["tiers"]]))
    R.ok("apagar um tier com filmes devolve-os a por classificar", p["apagado"]["livres"] == [A] and len(p["apagado"]["tiers"]) == 5, str(p["apagado"]))
    R.ok("sair da edição mostra nomes simples", p["fim"]["tiers"][1]["nome"] in ["10", "9", "8", "7", "6", "Novo", "Obras-primas"])
    R.ok("tudo persistiu ao recarregar", [t["id"] for t in x["tiers"]] == [t["id"] for t in p["fim"]["tiers"]]
         and any(t["nome"] == "Obras-primas" for t in x["tiers"]), str(x["tiers"]))

# ---- S10: pesquisa TMDB com fetch simulado (nunca toca na rede nem usa uma chave real)
MOCK = """
window.__pedidos = [];
window.fetch = async (url) => {
  const u = new URL(url); window.__pedidos.push(u.pathname + u.search.replace(/api_key=[^&]*/, 'api_key=X'));
  const chave = u.searchParams.get('api_key');
  const resp = (status, corpo) => ({ ok: status < 400, status, json: async () => corpo });
  if (chave === 'RUIM') return resp(401, { status_message: 'Invalid API key' });
  if (chave === 'REDE') throw new TypeError('Failed to fetch');
  if (u.pathname.endsWith('/search/movie')) return resp(200, { results: [
    { id: 11, title: 'Filme Um', release_date: '1999-05-01', poster_path: '/a.jpg' },
    { id: 12, title: 'Sem Imdb', release_date: '2001-01-01', poster_path: null } ] });
  if (u.pathname.endsWith('/movie/11/external_ids')) return resp(200, { imdb_id: 'tt0000011' });
  if (u.pathname.endsWith('/movie/12/external_ids')) return resp(200, { imdb_id: null });
  return resp(404, {});
};
"""
PROCURAR = """
const procurar = async (txt) => { const q = $('#tl-q'); q.value = txt; q.dispatchEvent(new Event('input', { bubbles: true })); await wait(700); };
const estadoBusca = () => ({ chave: !$('#tl-chave').hidden, msg: $('#tl-msg').hidden ? null : $('#tl-msg').textContent,
  res: $$('#tl-resultados li').map((l) => l.textContent), pedidos: [...window.__pedidos], guardada: localStorage.getItem('filmes-tv:tmdb-chave') });
"""
r = cena("S10a  pesquisa sem chave pede a chave", query="?v=tierlist", pre=MOCK, cenario=PROCURAR + """
  await procurar('filme'); const semChave = estadoBusca();
  $('#tl-chave-input').value = 'BOA'; await click($('#tl-chave-ok'));
  await procurar('filme'); return { semChave, comChave: estadoBusca() };""")
if r:
    x = r["r"]
    R.ok("sem chave não faz pedidos e mostra o campo da chave", x["semChave"]["chave"] and x["semChave"]["pedidos"] == [], str(x["semChave"]))
    R.ok("guarda a chave neste browser", x["comChave"]["guardada"] == "BOA" and not x["comChave"]["chave"])
    R.ok("mostra os resultados", len(x["comChave"]["res"]) == 2 and "Filme Um" in x["comChave"]["res"][0], str(x["comChave"]["res"]))
    R.ok("a pesquisa usa pt-PT", any("language=pt-PT" in p for p in x["comChave"]["pedidos"]))

r = cena("S10b  escolher um resultado", query="?v=tierlist", pre=MOCK + "localStorage.setItem('filmes-tv:tmdb-chave','BOA');", cenario=PROCURAR + """
  await procurar('filme');
  await click($$('#tl-resultados button')[0]); await wait(300);
  const aposAdicionar = { s: snap(), marcas: localStorage.getItem('filmes-tv:marcas'), busca: estadoBusca() };
  await procurar('filme'); await click($$('#tl-resultados button')[0]); await wait(300);
  const duplicado = estadoBusca();
  await procurar('filme'); await click($$('#tl-resultados button')[1]); await wait(300);
  return { aposAdicionar, duplicado, semImdb: estadoBusca(), final: snap() };""")
if r:
    x = r["r"]
    R.ok("o filme entra em por classificar", x["aposAdicionar"]["s"]["livres"] == ["tt0000011"], str(x["aposAdicionar"]["s"]["livres"]))
    R.ok("fica marcado como visto", "tt0000011" in json.loads(x["aposAdicionar"]["marcas"])["vistos"])
    R.ok("repetido: mensagem e nada duplicado", x["duplicado"]["msg"] and "já está" in x["duplicado"]["msg"] and x["final"]["livres"] == ["tt0000011"], str(x["duplicado"]["msg"]))
    R.ok("sem ID do IMDb: mensagem e nada adicionado", x["semImdb"]["msg"] and "IMDb" in x["semImdb"]["msg"] and len(x["final"]["livres"]) == 1)

r = cena("S10c  chave recusada (401) e sem rede", query="?v=tierlist", pre=MOCK + "localStorage.setItem('filmes-tv:tmdb-chave','RUIM');",
         cenario=PROCURAR + """
  await procurar('filme'); const recusada = estadoBusca();
  localStorage.setItem('filmes-tv:tmdb-chave', 'REDE');
  await procurar('outro'); const semRede = estadoBusca();
  return { recusada, semRede, tiers: snap().tiers.length };""")
if r:
    x = r["r"]
    R.ok("401 apaga a chave e pede outra", x["recusada"]["guardada"] is None and x["recusada"]["chave"], str(x["recusada"]))
    R.ok("sem rede: mensagem e a tierlist continua", x["semRede"]["msg"] and "ligação" in x["semRede"]["msg"] and x["tiers"] == 5, str(x["semRede"]["msg"]))

# ---- S11: exportar / importar (Review Focus 1)
r = cena("S11  exportar e importar", query="?v=tierlist", cenario=f"""
  window.FilmesTV.marcarVisto('{A}'); await wait(100);
  T().soltar('{A}', 't2', 0); await wait(100);
  let descarregado = null;
  const criar = URL.createObjectURL;
  URL.createObjectURL = (blob) => {{ descarregado = blob; return criar.call(URL, blob); }};
  await click($('#tl-exportar')); await wait(200);
  const texto = descarregado ? await descarregado.text() : null;
  window.alert = () => {{}};
  window.confirm = () => false;
  const recusado = T().importarTexto(texto); const semMudar = snap();
  T().soltar('{A}', 't4', 0); await wait(100);
  window.confirm = () => true;
  const mau = T().importarTexto('isto não é json'); const aposMau = snap();
  const bom = T().importarTexto(texto); await wait(150);
  return {{ texto, recusado, semMudar, mau, aposMau, bom, fim: snap(), marcas: localStorage.getItem('filmes-tv:marcas') }};""")
if r:
    x = r["r"]
    R.ok("exportar gera JSON com a versão e o filme", x["texto"] and json.loads(x["texto"])["v"] == 1 and A in json.loads(x["texto"])["itens"])
    R.ok("importar recusado pelo utilizador não muda nada", x["recusado"] is False and x["semMudar"]["tiers"][1]["filmes"] == [A])
    R.ok("ficheiro inválido é recusado e a tierlist fica como estava", x["mau"] is False and x["aposMau"]["tiers"][3]["filmes"] == [A], str(x["aposMau"]["tiers"]))
    R.ok("importar válido substitui a tierlist", x["bom"] is True and x["fim"]["tiers"][1]["filmes"] == [A] and x["fim"]["tiers"][3]["filmes"] == [])
    R.ok("os importados contam como vistos", A in json.loads(x["marcas"])["vistos"])

# ---- S12: localStorage bloqueado
BLOQUEIO = "Object.defineProperty(window, 'localStorage', { get() { throw new Error('bloqueado'); } });"
r = cena("S12  armazenamento bloqueado", query="?v=tierlist", pre=BLOQUEIO, cenario=f"""
  const inicio = {{ aviso: !$('#tl-aviso').hidden }};
  window.FilmesTV.marcarVisto('{A}'); await wait(100);
  T().soltar('{A}', 't1', 0); await wait(100);
  return {{ inicio, aviso: !$('#tl-aviso').hidden, tier: $$('#tl-tiers .tl-tier')[0].querySelectorAll('.tl-card').length }};""")
if r:
    x = r["r"]
    R.ok("mostra o aviso de que só vale nesta sessão", x["aviso"])
    R.ok("continua a funcionar em memória", x["tier"] == 1)

# ---- S13: o ✕ só aparece com hover ou ao tocar num cartão
r = cena("S13  ✕ de remover escondido até ser preciso", query="?v=tierlist", cenario=f"""
  window.FilmesTV.marcarVisto('{A}', '{B}'); await wait(100);
  T().soltar('{A}', 't1', 0); T().soltar('{B}', 't1', 1); await wait(100);
  const card = (id) => $('#tl-tiers .tl-card[data-film="' + id + '"]');
  const est = () => ({{ sel: $$('.tl-sel').map((c) => c.dataset.film),
    x: Object.fromEntries([['{A}', 0], ['{B}', 0]].map(([id]) => [id, getComputedStyle($('.tl-x', card(id))).opacity])) }});
  const inicio = est();
  await click(card('{A}')); const a = est();
  await click(card('{B}')); const b = est();
  await click(card('{B}')); const desmarca = est();
  await click(card('{A}')); await click($('#tl-tiers .tl-label')); const vazio = est();
  await click(card('{A}')); await click(document.body); const fora = est();
  await click(card('{A}')); await click($('.tl-x', card('{A}'))); await wait(100);
  return {{ inicio, a, b, desmarca, vazio, fora, livres: snap().livres, selDepois: est ? $$('.tl-sel').length : 0 }};""")
if r:
    x = r["r"]
    R.ok("o ✕ está escondido por omissão", all(v == "0" for v in x["inicio"]["x"].values()), str(x["inicio"]))
    R.ok("tocar num cartão seleciona-o e mostra o ✕", x["a"]["sel"] == [A] and x["a"]["x"][A] == "1" and x["a"]["x"][B] == "0", str(x["a"]))
    R.ok("tocar noutro passa a seleção", x["b"]["sel"] == [B] and x["b"]["x"][A] == "0" and x["b"]["x"][B] == "1", str(x["b"]))
    R.ok("tocar outra vez no mesmo desmarca", x["desmarca"]["sel"] == [])
    R.ok("tocar na etiqueta do tier limpa a seleção", x["vazio"]["sel"] == [])
    R.ok("tocar fora da tierlist limpa a seleção", x["fora"]["sel"] == [])
    R.ok("o ✕ continua a devolver o filme a por classificar", x["livres"] == [A], str(x["livres"]))
    R.ok("a seleção desaparece depois de remover", x["selDepois"] == 0)

# ---- S14: o press longo num poster não pode abrir o menu do browser ("abrir imagem noutro separador"), que cancela o arrasto
r = cena("S14  menu de contexto sobre os posters", query="?v=tierlist", cenario=f"""
  window.FilmesTV.marcarVisto('{A}', '{B}'); await wait(100);
  T().soltar('{A}', 't1', 0); await wait(100);
  const prova = (alvo) => {{ const ev = new MouseEvent('contextmenu', {{ bubbles: true, cancelable: true }}); alvo.dispatchEvent(ev); return ev.defaultPrevented; }};
  const imgTier = $('#tl-tiers .tl-card[data-film="{A}"] img'), imgLivre = $('#tl-livres .tl-card[data-film="{B}"] img');
  const css = (e) => ({{ pe: getComputedStyle(e).pointerEvents, sel: getComputedStyle(e.closest('.tl-card')).userSelect }});
  return {{ tierImg: prova(imgTier), livreImg: prova(imgLivre), tierCartao: prova(imgTier.closest('.tl-card')),
    fora: prova($('#tl-tiers .tl-label')), css: css(imgTier), cssLivre: css(imgLivre) }};""")
if r:
    x = r["r"]
    R.ok("o menu sobre o poster num tier é evitado", x["tierImg"] and x["tierCartao"], str(x))
    R.ok("o menu sobre o poster em por classificar é evitado", x["livreImg"], str(x))
    R.ok("o menu fora dos cartões não é mexido", not x["fora"], str(x))
    R.ok("a imagem não recebe o toque (o cartão é que o recebe) e o texto não se seleciona",
         x["css"]["pe"] == "none" and x["css"]["sel"] == "none" and x["cssLivre"]["pe"] == "none", str(x["css"]))

R.fim()
