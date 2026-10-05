import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from filmes_tv import now_lisbon


class FusoTest(unittest.TestCase):
    def test_hora_de_lisboa_sem_fuso(self):
        n = now_lisbon()
        self.assertIsNone(n.tzinfo)   # as horas dos programas também são datetimes sem fuso
        esperado = datetime.now(ZoneInfo("Europe/Lisbon")).replace(tzinfo=None)
        self.assertLess(abs(n - esperado), timedelta(seconds=2))


if __name__ == "__main__":
    unittest.main()
