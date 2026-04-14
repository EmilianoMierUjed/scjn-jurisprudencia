"""
Tests de los filtros: presets de instancia y normalización de épocas.

Cubren el segundo bug de v1.0 (filtro de época con LIKE sobre acentos).
"""

import pytest

from scjn_core import search
from scjn_core.filters import (
    EPOCAS_CANONICAS,
    INSTANCIA_PRESETS,
    _normalizar_epoca,
)


# ── Normalización de épocas ─────────────────────────────────────────────
class TestNormalizarEpoca:

    @pytest.mark.parametrize("entrada,esperado", [
        ("decima", "Décima Época"),
        ("Decima", "Décima Época"),
        ("Décima", "Décima Época"),
        ("DECIMA", "Décima Época"),
        ("decima epoca", "Décima Época"),
        ("Décima Época", "Décima Época"),
        ("DÉCIMA ÉPOCA", "Décima Época"),
        ("10", "Décima Época"),
        ("undecima", "Undécima Época"),
        ("Undécima", "Undécima Época"),
        ("11", "Undécima Época"),
        ("duodecima", "Duodécima Época"),
        ("12", "Duodécima Época"),
        ("novena", "Novena Época"),
        ("9", "Novena Época"),
    ])
    def test_acepta_variantes(self, entrada, esperado):
        assert _normalizar_epoca(entrada) == esperado

    def test_devuelve_none_para_basura(self):
        assert _normalizar_epoca("") is None
        assert _normalizar_epoca("xyz") is None
        assert _normalizar_epoca(None) is None


# ── Filtro de épocas end-to-end contra la BD ───────────────────────────
class TestFiltroEpocaEnBD:

    def test_decima_y_Décima_dan_mismo_resultado(self, conn):
        output_minus = search.buscar_jurisprudencia(
            conn,
            terminos=["interes superior del menor"],
            epocas=["decima"],
            limite=5,
        )
        output_plus = search.buscar_jurisprudencia(
            conn,
            terminos=["interes superior del menor"],
            epocas=["Décima Época"],
            limite=5,
        )
        assert output_minus == output_plus

    def test_arabigo_da_mismo_resultado_que_palabra(self, conn):
        a = search.buscar_jurisprudencia(
            conn,
            terminos=["pension alimenticia"],
            epocas=["10"],
            limite=5,
        )
        b = search.buscar_jurisprudencia(
            conn,
            terminos=["pension alimenticia"],
            epocas=["decima"],
            limite=5,
        )
        assert a == b

    def test_filtro_epoca_no_trae_otra_epoca(self, conn):
        output = search.buscar_jurisprudencia(
            conn,
            terminos=["amparo"],
            epocas=["undecima"],
            limite=10,
        )
        # No debería tener Novena ni Octava ni Décima
        assert "Novena Época" not in output
        assert "Octava Época" not in output
        # Décima podría aparecer si una tesis tiene "Décima" en su rubro,
        # pero no como campo Epoca:
        assert "Epoca: Décima Época" not in output
        assert "Epoca: Novena Época" not in output


# ── Presets de instancia ───────────────────────────────────────────────
class TestInstanciaPresets:

    def test_todos_los_presets_compilan_en_sql(self, conn):
        """Cada preset debe ser un fragmento SQL válido."""
        for preset, sql in INSTANCIA_PRESETS.items():
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM tesis t WHERE {sql}"
            )
            count = cursor.fetchone()[0]
            assert count >= 0, f"Preset {preset} produce SQL inválido"

    def test_pleno_scjn_no_devuelve_salas(self, conn):
        cursor = conn.execute(
            f"SELECT t.organo_juris FROM tesis t WHERE {INSTANCIA_PRESETS['pleno_scjn']} LIMIT 100"
        )
        for (organo,) in cursor.fetchall():
            assert "sala" not in (organo or "").lower(), (
                f"Pleno SCJN preset trajo Sala: {organo}"
            )

    def test_salas_scjn_no_devuelve_pleno(self, conn):
        cursor = conn.execute(
            f"SELECT t.organo_juris FROM tesis t WHERE {INSTANCIA_PRESETS['salas_scjn']} LIMIT 100"
        )
        for (organo,) in cursor.fetchall():
            assert (organo or "").lower().find("sala") >= 0
