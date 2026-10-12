import unittest

import requests

import filmes_tv


class FakeResponse:
    def __init__(self, status=200, text="ok"):
        self.status_code, self.text = status, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


class GetTest(unittest.TestCase):
    def setUp(self):
        self.esperas, self.pedidos = [], []
        self._sleep, self._session_get = filmes_tv.time.sleep, filmes_tv.session.get
        filmes_tv.time.sleep = self.esperas.append
        self.addCleanup(lambda: (setattr(filmes_tv.time, "sleep", self._sleep), setattr(filmes_tv.session, "get", self._session_get)))

    def respostas(self, *itens):
        itens = list(itens)

        def falso(url, timeout=None):
            self.pedidos.append(url)
            item = itens.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        filmes_tv.session.get = falso

    def test_repete_depois_de_um_timeout_e_acaba_por_conseguir(self):
        self.respostas(requests.ConnectTimeout("x"), requests.ConnectionError("y"), FakeResponse(text="página"))
        self.assertEqual(filmes_tv.get("https://exemplo/"), "página")
        self.assertEqual(len(self.pedidos), 3)
        self.assertEqual(self.esperas[1:], list(filmes_tv.RETRY_WAITS))   # a 1.ª espera é a pausa normal entre pedidos

    def test_desiste_ao_fim_das_tentativas(self):
        self.respostas(*[requests.ConnectTimeout("x")] * 3)
        with self.assertRaises(requests.ConnectTimeout):
            filmes_tv.get("https://exemplo/")
        self.assertEqual(len(self.pedidos), 3)

    def test_repete_em_erros_5xx(self):
        self.respostas(FakeResponse(503), FakeResponse(text="ok"))
        self.assertEqual(filmes_tv.get("https://exemplo/"), "ok")
        self.assertEqual(len(self.pedidos), 2)

    def test_nao_repete_em_404(self):
        self.respostas(FakeResponse(404))
        with self.assertRaises(requests.HTTPError):
            filmes_tv.get("https://exemplo/")
        self.assertEqual(len(self.pedidos), 1)


class DescobrirSlugsTest(unittest.TestCase):
    def test_sem_a_pagina_de_canais_usa_os_slugs_conhecidos(self):
        guardado = filmes_tv.get

        def falha(url):
            raise requests.ConnectTimeout("timeout")

        filmes_tv.get = falha
        self.addCleanup(setattr, filmes_tv, "get", guardado)
        slugs = filmes_tv.discover_slugs()
        self.assertEqual(slugs, {nome: filmes_tv.KNOWN_SLUGS[nome] for nome in filmes_tv.CHANNELS})
        self.assertEqual(len(slugs), 16)


if __name__ == "__main__":
    unittest.main()
