"""
Ranking por fuerza vinculante (Art. 217 Ley de Amparo).

El ORDER BY canónico jerarquiza las tesis por:
  1. Jurisprudencia antes que tesis aislada.
  2. Bucket por órgano emisor:
       0 = Pleno SCJN              (máxima fuerza vinculante)
       1 = Primera / Segunda Sala SCJN
       2 = Plenos Regionales
       3 = Plenos de Circuito
       4 = Tribunales Colegiados de Circuito
       5 = Otros
  3. Rank BM25 (cuando hay FTS5).
  4. Año DESC.

CRITICAL: la BD guarda "Suprema Corte de Justicia de la Nación" en `instancia`
para TODO lo de SCJN; el detalle Pleno/Sala vive en `organo_juris`. Antes
v1.0 miraba solo `instancia` y mandaba 205k tesis de SCJN al bucket "otros",
invirtiendo la promesa del producto. v1.1 lo arregló añadiendo el chequeo
sobre `organo_juris`.
"""

ORDEN_VINCULANTE_SQL = """
    CASE WHEN LOWER(t.tipo_tesis) LIKE '%jurisprudencia%' THEN 0 ELSE 1 END,
    CASE
        WHEN t.instancia = 'Suprema Corte de Justicia de la Nación'
             AND LOWER(t.organo_juris) LIKE 'pleno%' THEN 0
        WHEN t.instancia = 'Suprema Corte de Justicia de la Nación'
             AND LOWER(t.organo_juris) LIKE '%sala%' THEN 1
        WHEN LOWER(t.instancia) LIKE '%plenos regionales%' THEN 2
        WHEN LOWER(t.instancia) LIKE '%plenos de circuito%' THEN 3
        WHEN LOWER(t.instancia) LIKE '%tribunales colegiados%' THEN 4
        ELSE 5
    END
"""


def build_order_by(orden: str, usa_fts: bool) -> str:
    """Devuelve la cláusula ORDER BY acorde al modo elegido.

    Modos:
      - "vinculancia" (default) → fuerza vinculante + BM25 + año
      - "relevancia"            → BM25 puro (solo si hay FTS)
      - "reciente"              → año DESC
    """
    orden = (orden or "vinculancia").strip().lower()
    if orden == "relevancia" and usa_fts:
        return "rank_score ASC, t.anio DESC"
    if orden == "reciente":
        return "t.anio DESC, t.id_tesis DESC"
    # default: vinculancia (con desempate por relevancia si hay FTS, si no por año)
    if usa_fts:
        return f"{ORDEN_VINCULANTE_SQL}, rank_score ASC, t.anio DESC"
    return f"{ORDEN_VINCULANTE_SQL}, t.anio DESC"


def nivel_vinculante(row: dict) -> str:
    """Calcula la etiqueta S/A/B/C/D/E/F para una tesis.

    S = Pleno SCJN (jurisprudencia)
    A = Salas SCJN (jurisprudencia)
    B = Plenos Regionales (jurisprudencia)
    C = Plenos de Circuito (jurisprudencia)
    D = TCC (jurisprudencia)
    E = Aislada SCJN
    F = Aislada TCC u otros
    """
    tipo = (row.get("tipo_tesis") or "").lower()
    instancia = (row.get("instancia") or "")
    organo = (row.get("organo_juris") or "").lower()
    es_juris = "jurisprudencia" in tipo
    es_scjn = instancia == "Suprema Corte de Justicia de la Nación"

    if es_juris:
        if es_scjn and organo.startswith("pleno"):
            return "S"  # Pleno SCJN
        if es_scjn and "sala" in organo:
            return "A"  # Salas SCJN
        if "plenos regionales" in instancia.lower():
            return "B"
        if "plenos de circuito" in instancia.lower():
            return "C"
        if "tribunales colegiados" in instancia.lower():
            return "D"
        return "D"
    else:
        if es_scjn:
            return "E"  # Aislada SCJN
        return "F"  # Aislada TCC u otros
