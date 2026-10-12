#!/usr/bin/env python3
"""A pesquisa da página (título, título original, ator, "Sem correspondência") tem de dar o que o oráculo calcula.

O oráculo parte do `data-search` e do `data-cast` da página gerada: um filme casa se o título tem todas as
palavras OU se um mesmo ator as tem. Compara filmes, linha "Com ...", nomes a negrito, contagens e a lista
"Sem correspondência", e ainda o caminho de escrever no campo e de limpar com o ✕.
Uso: python tools/verificar_pesquisa.py
"""
import random
from collections import Counter
from urllib.parse import quote

from bs4 import BeautifulSoup

from _nav import TMP, Resultados, dump, f, gerar

now, HTML = gerar()
T = f.epoch(now) * 1000
SONDA = HTML + "<script>setTimeout(() => { document.body.dataset.valor = document.getElementById('q').value; }, 300);</script>"
(TMP / "sonda.html").write_text(SONDA, encoding="utf-8")


def ver_filme(li):
    linha = li.select_one("p.cast")
    return (li["data-film"], linha.get_text() if linha else None, tuple(m.get_text() for m in li.select("p.cast mark")))


def estado(dom):
    soup = BeautifulSoup(dom, "html.parser")
    out = {}
    for sid in ("agora", "gravar", "vir"):
        sec = soup.select_one(f"section#{sid}")
        out[sid] = dict(films=[ver_filme(li) for li in sec.select("ol.films > li.film")],
                        count=sec.select_one("h2 .count").get_text(),
                        nav=soup.select_one(f".jump a[href='#{sid}'] b").get_text(),
                        hidden=sec.has_attr("hidden"), empty_hidden=sec.select_one(".empty").has_attr("hidden"),
                        empty_text=sec.select_one(".empty").get_text())
    det = soup.select_one("details")
    out["sem"] = dict(open=det.has_attr("open"), count=det.select_one("summary .count").get_text(),
                      visible=sum(not li.has_attr("hidden") for li in det.select("ul > li")))
    out["ui"] = dict(value=soup.body.get("data-valor", ""), clear_hidden=soup.select_one(".clear").has_attr("hidden"))
    return out


base = BeautifulSoup(HTML, "html.parser")
recs = {sid: [dict(id=li["data-film"], hay=li["data-search"], cast=li["data-cast"].split("|") if li.has_attr("data-cast") else [])
              for li in base.select(f"section#{sid} ol.films > li.film")] for sid in ("agora", "gravar", "vir")}
unm = [li["data-search"] for li in base.select("details ul > li")]


def esperado(q):
    toks = f.search_key(q).split()
    out = {}
    for sid, films in recs.items():
        lista = []
        for r in films:
            hits = [i for i, n in enumerate(r["cast"]) if toks and all(t in f.search_key(n) for t in toks)]
            if toks and not (all(t in r["hay"] for t in toks) or hits):
                continue
            if r["cast"]:
                idx = sorted({i for i in (0, 1, 2) if i < len(r["cast"])} | set([i for i in hits if i > 2][:3]))
                texto, marcas = "Com " + ", ".join(r["cast"][i] for i in idx), tuple(r["cast"][i] for i in idx if i in hits)
            else:
                texto, marcas = None, ()
            lista.append((r["id"], texto, marcas))
        n = len(lista)
        out[sid] = dict(films=lista, count=str(n), nav=str(n), hidden=(sid == "agora" and n == 0), empty_hidden=n > 0,
                        empty_text="Nenhum resultado" if toks else "Nada de momento.")
    m = sum(all(t in h for t in toks) for h in unm)
    out["sem"] = dict(open=bool(toks) and m > 0, count=str(m if toks else len(unm)), visible=m if toks else len(unm))
    out["ui"] = dict(value=q, clear_hidden=not q)
    return out


rnd = random.Random(7)
titulos = [li.select_one("h3 a").get_text() for li in base.select("section#gravar ol.films > li.film")]
sem = [li.get_text() for li in base.select("details ul > li")]
atores = Counter(n for sid in recs for r in recs[sid] for n in set(r["cast"]))
com_elenco = [r for sid in recs for r in recs[sid] if len(r["cast"]) >= 8]
r1 = rnd.choice(com_elenco)
frequente = atores.most_common(1)[0][0]
consultas = [
    "", "mumia", "MÚMIA", "the mummy", "salt arca", "zzzzzz", "a", "chip n dale", "   ", "乱",       # título
    rnd.choice(titulos).split()[0], " ".join(rnd.choice(titulos).split()[:2]),
    f.search_key(rnd.choice(sem)).split()[0],                                                        # sem correspondência
    frequente, frequente.split()[-1], frequente.upper(),                                             # ator
    r1["cast"][6], r1["cast"][6].split()[0],                                                         # ator fora dos 3 primeiros
    r1["cast"][0].split()[0] + " " + r1["cast"][1].split()[-1],                                      # nome de A + apelido de B: 0
    "tom hanks",
]
r = Resultados()
for q in consultas:
    obtido, exp = estado(dump(f"file://{TMP / 'sonda.html'}?t={T}" + (f"&q={quote(q)}" if q else ""))), esperado(q)
    resumo = {k: obtido[k]["count"] for k in ("agora", "gravar", "vir")}
    r.ok(f"?q={q!r:34s} {resumo} sem-corresp={obtido['sem']['visible']}", obtido == exp)

# escrever no campo (com acento) e limpar com o ✕
teste = HTML + """<script>
setTimeout(() => {
  const q = document.getElementById('q');
  q.value = 'Múmia'; q.dispatchEvent(new Event('input', {bubbles: true}));
  setTimeout(() => {
    document.body.dataset.depois = document.querySelector('#gravar h2 .count').textContent;
    document.querySelector('.clear').click();
    setTimeout(() => {
      document.body.dataset.limpo = document.querySelector('#gravar h2 .count').textContent;
      document.body.dataset.valor = document.getElementById('q').value;
    }, 600);
  }, 600);
}, 300);
</script>"""
(TMP / "escrever.html").write_text(teste, encoding="utf-8")
d = BeautifulSoup(dump(f"file://{TMP / 'escrever.html'}?t={T}", 8000), "html.parser").body.attrs
r.ok("escrever 'Múmia' dá o esperado em Para gravar", d.get("data-depois") == esperado("Múmia")["gravar"]["count"], str(d.get("data-depois")))
r.ok("clicar ✕ repõe a lista toda e esvazia o campo", d.get("data-limpo") == esperado("")["gravar"]["count"] and d.get("data-valor") == "")
r.fim()
