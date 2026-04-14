"""
Smoke tests de las 10 funciones de búsqueda.

No validan el contenido jurídico, solo que cada función responde sin
errores y produce output con la estructura esperada.
"""

import pytest

from scjn_core import search


class TestBuscarJurisprudencia:

    def test_devuelve_resultados_para_termino_comun(self, conn):
        out = search.buscar_jurisprudencia(conn, terminos=["amparo"], limite=5)
        assert "Resultado" in out

    def test_lista_terminos_alternativos(self, conn):
        out = search.buscar_jurisprudencia(
            conn, terminos=["despido injustificado", "despido sin causa"], limite=5,
        )
        assert "Resultado" in out

    def test_solo_jurisprudencia(self, conn):
        out = search.buscar_jurisprudencia(
            conn, terminos=["amparo"], solo_jurisprudencia=True, limite=5,
        )
        assert "Tipo: Aislada" not in out

    def test_terminos_vacios_devuelve_error(self, conn):
        out = search.buscar_jurisprudencia(conn, terminos=[])
        assert "Error" in out

    def test_caracteres_especiales_no_revientan(self, conn):
        # Caracteres FTS5 reservados — el sanitize debe limpiarlos
        out = search.buscar_jurisprudencia(
            conn, terminos=['"despido*"', "(prueba)"], limite=3,
        )
        # No debería levantar excepción ni devolver error de sintaxis
        assert "fts5: syntax error" not in out


class TestBuscarInterseccion:

    def test_dos_conceptos(self, conn):
        out = search.buscar_interseccion(
            conn,
            concepto_a=["despido injustificado"],
            concepto_b=["carga de la prueba"],
            limite=5,
        )
        assert "Resultado" in out or "Sin resultados" in out

    def test_tres_conceptos(self, conn):
        out = search.buscar_interseccion(
            conn,
            concepto_a=["amparo"],
            concepto_b=["suspension"],
            concepto_c=["despido"],
            limite=5,
        )
        assert "resultado" in out.lower() or "Sin resultados" in out

    def test_concepto_vacio_devuelve_error(self, conn):
        out = search.buscar_interseccion(conn, concepto_a=[], concepto_b=["prueba"])
        assert "Error" in out


class TestBuscarProximidad:

    def test_near_basico(self, conn):
        out = search.buscar_proximidad(
            conn,
            termino_a="despido",
            termino_b="carga de la prueba",
            distancia=20,
            limite=5,
        )
        assert "fts5" not in out.lower() or "resultado" in out.lower()


class TestBuscarRubro:

    def test_busqueda_solo_en_rubro(self, conn):
        out = search.buscar_rubro(conn, terminos=["pension alimenticia"], limite=5)
        assert "Resultado" in out or "Sin resultados" in out


class TestLeerTesis:

    @pytest.fixture
    def primer_id(self, conn):
        """Devuelve un id_tesis válido cualquiera para probar la lectura."""
        cur = conn.execute("SELECT id_tesis FROM tesis LIMIT 1")
        return cur.fetchone()[0]

    def test_leer_por_id(self, conn, primer_id):
        out = search.leer_tesis_completa(conn, identificador=primer_id)
        assert "Texto completo" in out

    def test_leer_id_inexistente(self, conn):
        out = search.leer_tesis_completa(conn, identificador="ID_QUE_NO_EXISTE_99999")
        assert "No se encontro" in out

    def test_leer_varias(self, conn, primer_id):
        out = search.leer_varias_tesis(conn, identificadores=[primer_id])
        assert "Texto completo" in out

    def test_leer_varias_vacio(self, conn):
        out = search.leer_varias_tesis(conn, identificadores=[])
        assert "Error" in out


class TestExplorarValores:

    def test_campo_permitido(self, conn):
        out = search.explorar_valores(conn, campo="instancia", limite=5)
        assert "tesis" in out.lower()

    def test_campo_no_permitido(self, conn):
        out = search.explorar_valores(conn, campo="DROP TABLE", limite=5)
        assert "no permitido" in out.lower()


class TestInfoBaseDatos:

    def test_estructura_basica(self, conn):
        out = search.info_base_datos(conn)
        assert "Total de criterios" in out
        assert "Rango temporal" in out
        assert "Indice FTS5" in out
        assert "Desglose por instancia" in out
