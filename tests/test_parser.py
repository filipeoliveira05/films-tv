import unittest
from datetime import date, datetime
from pathlib import Path

from filmes_tv import parse_programs

FIX = Path(__file__).parent / "fixtures"


def ler(nome):
    return (FIX / nome).read_text(encoding="utf-8")


class ParseProgramsTest(unittest.TestCase):
    def test_pagina_normal(self):
        progs = parse_programs(ler("hollywood_hoje.html"), date(2026, 10, 5))
        self.assertEqual(len(progs), 4)
        self.assertEqual(progs[0], (datetime(2026, 10, 5, 1, 10), datetime(2026, 10, 5, 3, 5), "Gunner"))
        self.assertEqual(progs[2][2], "Ricky Stanicky")

    def test_carry_over_da_noite_anterior(self):
        # a página de terça abre com o programa de segunda 23:10 às 00:55
        progs = parse_programs(ler("hollywood_terca.html"), date(2026, 10, 6))
        self.assertEqual(
            progs[0],
            (datetime(2026, 10, 5, 23, 10), datetime(2026, 10, 6, 0, 55), "Golpe ao Amanhecer"),
        )
        self.assertEqual(progs[1][0], datetime(2026, 10, 6, 0, 55))

    def test_programa_final_atravessa_meia_noite(self):
        progs = parse_programs(ler("hollywood_terca.html"), date(2026, 10, 6))
        self.assertEqual(
            progs[-1],
            (datetime(2026, 10, 6, 23, 55), datetime(2026, 10, 7, 1, 10), "Balas & Bolinhos"),
        )

    def test_sem_sobreposicoes(self):
        progs = parse_programs(ler("hollywood_terca.html"), date(2026, 10, 6))
        for a, b in zip(progs, progs[1:]):
            self.assertLessEqual(a[1], b[0])


if __name__ == "__main__":
    unittest.main()
