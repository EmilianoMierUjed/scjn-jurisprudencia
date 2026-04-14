"""
Tests de las 3 tools nuevas en v1.2.
"""

import pytest

from scjn_core import tools_v12
from scjn_core.tools_v12 import _parse_circuito


# ── _parse_circuito (lógica pura) ───────────────────────────────────────
class TestParseCircuito:

    @pytest.mark.parametrize("entrada,esperado", [
        (17, 17),
        ("17", 17),
        ("XVII", 17),
        ("xvii", 17),
        ("decimo septimo", 17),
        ("Décimo Séptimo", 17),
        ("4", 4),
        ("IV", 4),
        ("cuarto", 4),
        ("decimo", 10),
        ("decimo octavo", 18),
        ("vigesimo segundo", 22),
        ("primer", 1),
        ("xxxii", 32),
    ])
    def test_acepta_variantes(self, entrada, esperado):
        assert _parse_circuito(entrada) == esperado

    @pytest.mark.parametrize("entrada", [
        None, "", "0", "33", "abc", "circuito 5", 999, -1,
    ])
    def test_rechaza_invalidos(self, entrada):
        assert _parse_circuito(entrada) is None


# ── extraer_cita_oficial ────────────────────────────────────────────────
class TestExtraerCitaOficial:

    @pytest.fixture
    def id_real(self, conn):
        return conn.execute(
            "SELECT id_tesis FROM tesis WHERE tesis_codigo IS NOT NULL "
            "AND tesis_codigo != '' AND fuente IS NOT NULL LIMIT 1"
        ).fetchone()[0]

    def test_devuelve_cita_para_id_valido(self, conn, id_real):
        out = tools_v12.extraer_cita_oficial(conn, id_real)
        assert "Cita oficial" in out
        assert "Rubro" in out
        assert "registro digital" in out

    def test_id_inexistente(self, conn):
        out = tools_v12.extraer_cita_oficial(conn, "ID_QUE_NO_EXISTE_99999")
        assert "No se encontró" in out


# ── compilar_linea_jurisprudencial ──────────────────────────────────────
class TestLineaJurisprudencial:

    def test_devuelve_cronologia_agrupada(self, conn):
        out = tools_v12.compilar_linea_jurisprudencial(
            conn, tema=["interes superior del menor"], anio_minimo=2018, limite=10,
        )
        assert "Línea jurisprudencial" in out
        # Debe agrupar por época con el separador ══
        assert "══" in out

    def test_solo_jurisprudencia(self, conn):
        out = tools_v12.compilar_linea_jurisprudencial(
            conn, tema=["amparo"], anio_minimo=2020, limite=15,
        )
        # Solo jurisprudencias — no debe haber tesis aisladas en el output
        # (el output usa el formato compacto, así que verificamos que el
        # contenido no contenga "Aislada")
        assert "Aislada" not in out

    def test_tema_vacio(self, conn):
        out = tools_v12.compilar_linea_jurisprudencial(conn, tema=[])
        assert "Error" in out


# ── buscar_obligatorios_para_circuito ───────────────────────────────────
class TestObligatoriosCircuito:

    def test_circuito_17_acepta_int(self, conn):
        out = tools_v12.buscar_obligatorios_para_circuito(
            conn, circuito=17, terminos=["amparo"], limite=5,
        )
        assert "decimo septimo" in out.lower()

    def test_circuito_17_acepta_romano(self, conn):
        out = tools_v12.buscar_obligatorios_para_circuito(
            conn, circuito="XVII", terminos=["amparo"], limite=5,
        )
        assert "XVII" in out or "decimo septimo" in out.lower()

    def test_circuito_invalido(self, conn):
        out = tools_v12.buscar_obligatorios_para_circuito(
            conn, circuito="ABC", terminos=["amparo"],
        )
        assert "no reconocido" in out.lower()

    def test_terminos_vacios(self, conn):
        out = tools_v12.buscar_obligatorios_para_circuito(
            conn, circuito=17, terminos=[],
        )
        assert "Error" in out
