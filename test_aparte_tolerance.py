"""Testes da tolerância de 1 minuto no desconto de tempo do aparte."""

import re
import unittest
from pathlib import Path

MAIN_PATH = Path(__file__).parent / "main.py"


def carregar_tolerancia_segundos() -> int:
    texto = MAIN_PATH.read_text(encoding="utf-8")
    match = re.search(r"APARTE_TOLERANCE_SECONDS\s*=\s*(\d+)", texto)
    if not match:
        raise ValueError("APARTE_TOLERANCE_SECONDS não encontrada em main.py")
    return int(match.group(1))


def calcular_tempo_descontado(tempo_gasto: int, tolerancia: int) -> int:
    """Mesma regra usada em PainelPresidente.encerrar_aparte()."""
    return max(0, tempo_gasto - tolerancia)


def calcular_tempo_restante_orador(saved_main_seconds: int, tempo_gasto: int, tolerancia: int) -> int:
    descontado = calcular_tempo_descontado(tempo_gasto, tolerancia)
    restante = saved_main_seconds - descontado
    return max(0, restante)


class TestAparteTolerance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tolerancia = carregar_tolerancia_segundos()
        cls.main_source = MAIN_PATH.read_text(encoding="utf-8")

    def test_constante_definida_em_main(self):
        self.assertEqual(self.tolerancia, 60)

    def test_encerrar_aparte_usa_tolerancia(self):
        self.assertIn("tempo_descontado = max(0, tempo_gasto - APARTE_TOLERANCE_SECONDS)", self.main_source)
        self.assertIn("self.remaining_seconds = self.saved_main_seconds - tempo_descontado", self.main_source)

    def test_dentro_da_tolerancia_nao_desconta(self):
        t = self.tolerancia
        self.assertEqual(calcular_tempo_descontado(0, t), 0)
        self.assertEqual(calcular_tempo_descontado(45, t), 0)
        self.assertEqual(calcular_tempo_descontado(t, t), 0)

    def test_acima_da_tolerancia_desconta_excedente(self):
        t = self.tolerancia
        self.assertEqual(calcular_tempo_descontado(90, t), 30)
        self.assertEqual(calcular_tempo_descontado(180, t), 120)

    def test_restauracao_tempo_orador(self):
        t = self.tolerancia
        # Orador tinha 5 min; aparte usou 1 min 30 s -> desconta só 30 s
        self.assertEqual(calcular_tempo_restante_orador(300, 90, t), 270)
        # Aparte usou 45 s -> orador recupera tempo integral
        self.assertEqual(calcular_tempo_restante_orador(300, 45, t), 300)
        # Aparte usou 3 min -> desconta 2 min
        self.assertEqual(calcular_tempo_restante_orador(300, 180, t), 180)


if __name__ == "__main__":
    unittest.main(verbosity=2)
