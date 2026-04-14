"""
Tests del bug crítico v1.0 → v1.1: ranking por fuerza vinculante.

En v1.0, el ORDER BY miraba solo `instancia` y mandaba 205k tesis de SCJN
al bucket "otros" porque la distinción Pleno/Sala vivía en `organo_juris`.
Resultado: las tesis de Pleno SCJN aparecían DESPUÉS de TCCs en cualquier
búsqueda. Estos tests garantizan que el bug nunca regrese.
"""

import re

from scjn_core import search
from scjn_core.ranking import nivel_vinculante


# ── nivel_vinculante: lógica pura, sin BD ──────────────────────────────
class TestNivelVinculante:

    def test_pleno_scjn_jurisprudencia_es_S(self):
        row = {
            "tipo_tesis": "Jurisprudencia",
            "instancia": "Suprema Corte de Justicia de la Nación",
            "organo_juris": "Pleno",
        }
        assert nivel_vinculante(row) == "S"

    def test_primera_sala_jurisprudencia_es_A(self):
        row = {
            "tipo_tesis": "Jurisprudencia",
            "instancia": "Suprema Corte de Justicia de la Nación",
            "organo_juris": "Primera Sala",
        }
        assert nivel_vinculante(row) == "A"

    def test_segunda_sala_jurisprudencia_es_A(self):
        row = {
            "tipo_tesis": "Jurisprudencia",
            "instancia": "Suprema Corte de Justicia de la Nación",
            "organo_juris": "Segunda Sala",
        }
        assert nivel_vinculante(row) == "A"

    def test_tcc_jurisprudencia_es_D(self):
        row = {
            "tipo_tesis": "Jurisprudencia",
            "instancia": "Tribunales Colegiados de Circuito",
            "organo_juris": "Primer Tribunal Colegiado del Decimoséptimo Circuito",
        }
        assert nivel_vinculante(row) == "D"

    def test_aislada_scjn_es_E(self):
        row = {
            "tipo_tesis": "Aislada",
            "instancia": "Suprema Corte de Justicia de la Nación",
            "organo_juris": "Primera Sala",
        }
        assert nivel_vinculante(row) == "E"

    def test_aislada_tcc_es_F(self):
        row = {
            "tipo_tesis": "Aislada",
            "instancia": "Tribunales Colegiados de Circuito",
            "organo_juris": "Primer Tribunal Colegiado",
        }
        assert nivel_vinculante(row) == "F"

    def test_pleno_regional_jurisprudencia_es_B(self):
        row = {
            "tipo_tesis": "Jurisprudencia",
            "instancia": "Plenos Regionales",
            "organo_juris": "Pleno Regional en Materia Civil de la Región Centro-Sur",
        }
        assert nivel_vinculante(row) == "B"

    def test_pleno_circuito_jurisprudencia_es_C(self):
        row = {
            "tipo_tesis": "Jurisprudencia",
            "instancia": "Plenos de Circuito",
            "organo_juris": "Pleno del Decimoséptimo Circuito",
        }
        assert nivel_vinculante(row) == "C"


# ── Regresión del bug: SCJN debe aparecer ANTES que TCC ────────────────
class TestRegresionBugV10:
    """El test que protege contra el bug que invertía el ranking."""

    def _extraer_niveles(self, output: str) -> list[str]:
        """Extrae los niveles S/A/B/C/D/E/F del output formateado."""
        return re.findall(r"\(Nivel ([SABCDEF])\)", output)

    def test_busqueda_amplia_no_pone_TCC_antes_que_SCJN(self, conn):
        """En 'derecho a la salud' debe haber al menos un S/A en top 5."""
        output = search.buscar_jurisprudencia(
            conn,
            terminos=["derecho a la salud", "proteccion de la salud"],
            limite=10,
        )
        niveles = self._extraer_niveles(output)
        assert len(niveles) > 0, "El output debería tener niveles formateados"
        top5 = niveles[:5]
        # En el bug v1.0, el top 5 estaba lleno de D (TCC) y los S/A iban al final.
        # Después del fix, debe haber al menos uno de S/A en el top 5.
        assert any(n in ("S", "A") for n in top5), (
            f"Top 5 sin SCJN — posible regresión del bug v1.0. Niveles: {top5}"
        )

    def test_orden_jurisprudencia_antes_que_aislada(self, conn):
        """Las jurisprudencias (S-D) deben aparecer antes que las aisladas (E-F)."""
        output = search.buscar_jurisprudencia(
            conn,
            terminos=["amparo directo"],
            limite=20,
        )
        niveles = self._extraer_niveles(output)
        if not niveles:
            return  # nada que validar
        # Encontrar la primera aislada
        primera_aislada = None
        for i, n in enumerate(niveles):
            if n in ("E", "F"):
                primera_aislada = i
                break
        if primera_aislada is None:
            return  # solo jurisprudencias, perfecto
        # Después de la primera aislada, no debería haber jurisprudencias
        despues = niveles[primera_aislada:]
        assert all(n in ("E", "F") for n in despues), (
            f"Jurisprudencia después de aislada — orden roto. Niveles: {niveles}"
        )

    def test_filtro_pleno_scjn_solo_devuelve_pleno(self, conn):
        """instancia='pleno_scjn' no debe colar Salas ni TCCs."""
        output = search.buscar_jurisprudencia(
            conn,
            terminos=["amparo"],
            instancia="pleno_scjn",
            limite=10,
        )
        # Todos los resultados deben tener "Organo: Pleno" en su header.
        # Si hay aunque sea un "Primera Sala" o "Tribunales", el filtro está roto.
        assert "Primera Sala" not in output
        assert "Segunda Sala" not in output
        assert "Tribunales Colegiados" not in output

    def test_filtro_tcc_solo_devuelve_TCC(self, conn):
        output = search.buscar_jurisprudencia(
            conn,
            terminos=["pension alimenticia"],
            instancia="tcc",
            limite=10,
        )
        niveles = self._extraer_niveles(output)
        # tcc no debería traer ningún S/A/B/C
        assert all(n in ("D", "F") for n in niveles), (
            f"Filtro tcc trajo niveles fuera de D/F: {niveles}"
        )
