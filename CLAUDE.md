# Herramienta de Búsqueda de Jurisprudencia SCJN

## Base de datos

- **Archivo:** `data/scjn_tesis.db` (relativo a la raíz del proyecto)
- **Motor:** SQLite3 con FTS5 habilitado
- **Registros:** ~311,000 criterios (tesis aisladas y jurisprudencias)
- **Rango:** 1911 — 2026
- **Tabla principal:** `tesis`
- **Tabla FTS5:** `tesis_fts` (índice de texto completo sobre rubro, texto, precedentes, materias)

## Schema

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id_tesis | TEXT PK | Identificador único |
| rubro | TEXT | Título/encabezado de la tesis |
| epoca | TEXT | Época del Semanario Judicial |
| instancia | TEXT | Órgano emisor |
| organo_juris | TEXT | Órgano específico |
| fuente | TEXT | Publicación |
| tipo_tesis | TEXT | "Aislada" o "Jurisprudencia" |
| anio | INTEGER | Año de publicación |
| mes | TEXT | Mes |
| materias | TEXT | Materias separadas por coma |
| tesis_codigo | TEXT | Código de registro para cita formal |
| huella_digital | TEXT | Hash |
| texto | TEXT | Texto completo del criterio (avg ~1000 chars) |
| precedentes | TEXT | Casos originarios |
| fecha_descarga | TEXT | Timestamp de descarga |

> **v1.2:** la columna `json_completo` (JSON crudo de la API) se eliminó.
> Pesaba ~612 MB y nadie la leía en runtime. La BD bajó de 1.7 GB a
> ~990 MB. Si alguna vez se necesita el JSON original, se regenera desde
> la API SCJN con el `id_tesis`.

## Cómo buscar con FTS5

```sql
-- Búsqueda conceptual
SELECT t.id_tesis, t.rubro, t.tipo_tesis, t.instancia, t.anio, t.tesis_codigo,
       substr(t.texto, 1, 500) AS extracto
FROM tesis t
JOIN tesis_fts ON t.rowid = tesis_fts.rowid
WHERE tesis_fts MATCH '"derecho a la salud" OR "proteccion de la salud"'
ORDER BY CASE WHEN LOWER(t.tipo_tesis) LIKE '%jurisprudencia%' THEN 0 ELSE 1 END,
         t.anio DESC
LIMIT 30;

-- Búsqueda interseccional (A AND B)
SELECT t.id_tesis, t.rubro, t.tipo_tesis, t.instancia, t.anio, t.tesis_codigo,
       substr(t.texto, 1, 500) AS extracto
FROM tesis t
JOIN tesis_fts ON t.rowid = tesis_fts.rowid
WHERE tesis_fts MATCH '("despido injustificado" OR "despido sin causa") AND ("carga de la prueba")'
ORDER BY t.anio DESC
LIMIT 30;

-- Lectura completa
SELECT rubro, texto, precedentes, tipo_tesis, instancia, organo_juris, epoca, anio, tesis_codigo
FROM tesis WHERE id_tesis = 'ID_AQUI';
```

## FTS5: sintaxis MATCH

- Frase exacta: `"derecho a la salud"`
- OR: `"termino1" OR "termino2"`
- AND: `"concepto a" AND "concepto b"`
- Combinado: `("termino1" OR "termino2") AND ("termino3" OR "termino4")`
- FTS5 ignora acentos (tokenizer unicode61 remove_diacritics 2)

## Estructura del proyecto

```
Base_Datos_SCJN/
├── scjn_core/                ← Núcleo de búsqueda (paquete Python puro)
│   ├── search.py             ← 10 tools de búsqueda (funciones puras)
│   ├── tools_v12.py          ← 3 tools nuevas v1.2
│   ├── protocol.py           ← INSTRUCCIONES (protocolo 5 rondas)
│   ├── ranking.py            ← ORDEN_VINCULANTE_SQL + niveles S/A/B/C/D/E/F
│   ├── filters.py            ← INSTANCIA_PRESETS + normalización de épocas
│   ├── format.py             ← format_resultados con snippet
│   ├── fts.py                ← Sanitización FTS5
│   ├── errores.py            ← humanizar(exc) → mensajes accionables
│   ├── database.py           ← connect(), has_fts()
│   └── config.py             ← DB_PATH, MAX_*, get_logger
├── server/server.py          ← MCP wrapper delgado para Claude Desktop
├── cli/scjn_cli.py           ← CLI standalone con API Anthropic
├── updater/actualizar_bd.py  ← Actualizador incremental desde API SCJN
├── install/                  ← Instalador Windows + setup FTS5 + specs PyInstaller
├── scripts/                  ← validar_bd, baseline, eliminar_json_completo
├── tests/                    ← 82 tests pytest
├── docs/                     ← Instalación, USO_ABOGADO + materiales de venta
└── data/scjn_tesis.db        ← Base de datos (~990 MB, NO va en git)
```

## Tools del MCP (v1.2 — 13 en total)

| Tool | Propósito |
|------|-----------|
| `buscar_jurisprudencia` | OR de sinónimos + filtros (materia, instancia, órgano, años, épocas, buscar_en, orden) |
| `buscar_interseccion` | AND entre 2-3 conceptos (cada uno con OR interno) |
| `buscar_proximidad` | NEAR() de FTS5 — dos términos dentro de N tokens |
| `buscar_rubro` | Busca sólo en el rubro (más preciso) |
| `buscar_similares` | Dado un `id_tesis`, encuentra otras con rubro similar (BM25) |
| `buscar_contradiccion` | Jurisprudencias surgidas de contradicción de tesis/criterios |
| `leer_tesis_completa` | Texto completo + metadatos de una tesis |
| `leer_varias_tesis` | Lee hasta 15 tesis en una llamada (batch) |
| `explorar_valores` | Valores únicos de un campo (tipo_tesis, época, instancia, materias, órgano, fuente) |
| `info_base_datos` | Totales, rango temporal, por tipo/instancia/época, estado FTS |
| `extraer_cita_oficial` (v1.2) | Cita formal lista para pegar en escritos legales mexicanos |
| `compilar_linea_jurisprudencial` (v1.2) | Cronología de jurisprudencias sobre un tema, agrupada por época |
| `buscar_obligatorios_para_circuito` (v1.2) | Filtra criterios obligatorios para un circuito específico (1-32) |

## Orden por fuerza vinculante (v1.1)

El `ORDER BY` de las búsquedas jerarquiza por:
1. Jurisprudencia antes que tesis aislada
2. Bucket de órgano:
   - 0 = Pleno SCJN (`instancia='Suprema Corte...' AND organo_juris LIKE 'pleno%'`)
   - 1 = Salas SCJN (`... AND organo_juris LIKE '%sala%'`)
   - 2 = Plenos Regionales
   - 3 = Plenos de Circuito
   - 4 = Tribunales Colegiados de Circuito
   - 5 = Otros
3. Rank BM25 (si hay FTS5)
4. Año DESC

Niveles mostrados en el output: S (Pleno SCJN), A (Salas SCJN), B (Plenos
Regionales), C (Plenos de Circuito), D (TCC), E (Aislada SCJN), F (Aislada TCC).
