#!/usr/bin/env python3
"""A página gerada às `now` e aberta (?t=) a outras horas tem de ficar igual à que o Python geraria para essas horas.

Cobre: em que secção está cada emissão, "faltam/em", fita, estado urgente, contagens e secções escondidas.
Uso: python tools/verificar_horas.py
"""
import re
from datetime import timedelta

from bs4 import BeautifulSoup

from _nav import TMP, Resultados, dump, f, gerar


def extrair(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for sid in ("agora", "gravar", "vir"):
        sec = soup.select_one(f"section#{sid}")
        films = []
        for li in sec.select("ol.films > li.film"):
            emissoes = []
            for a in li.select("li.airing"):
                left, w = a.select_one(".left"), a.select_one(".track i")
                emissoes.append((a["data-start"], left.get_text() if left else None, "urgent" in a.get("class", []),
                                 float(re.search(r"([\d.]+)%", w["style"]).group(1)) if w else None))
            films.append((li["data-film"], tuple(emissoes)))
        nav = soup.select_one(f".jump a[href='#{sid}']")
        out[sid] = dict(films=films, count=sec.select_one("h2 .count").get_text(), nav=nav.select_one("b").get_text(),
                        nav_hidden=nav.has_attr("hidden"), sec_hidden=sec.has_attr("hidden"),
                        empty_hidden=sec.select_one(".empty").has_attr("hidden"))
    return out


r = Resultados()
n0, _ = gerar()
for nome, desvio in [("+0 (hora da geração)", timedelta(0)), ("+8h", timedelta(hours=8)), ("+1 dia", timedelta(days=1)),
                     ("+3 dias 5h", timedelta(days=3, hours=5)), ("+5 dias", timedelta(days=5)),
                     ("+6 dias 20h", timedelta(days=6, hours=20)), ("+9 dias", timedelta(days=9))]:
    agora = n0 + desvio
    _, oraculo_html = gerar(agora, "oraculo.html")
    esperado = extrair(oraculo_html)
    obtido = extrair(dump(f"file://{TMP / 'build.html'}?t={f.epoch(agora) * 1000}"))
    contagens = {k: v["count"] for k, v in obtido.items()}
    r.ok(f"{nome:22s} {contagens}", obtido == esperado)
r.fim()
