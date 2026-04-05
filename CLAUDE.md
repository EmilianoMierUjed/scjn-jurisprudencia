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
| json_completo | TEXT | JSON original de la API |
| fecha_descarga | TEXT | Timestamp de descarga |

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
├── server/server.py          ← MCP server (6 tools + protocolo de búsqueda)
├── updater/actualizar_bd.py  ← Actualizador incremental desde API SCJN
├── install/                  ← Instalador Windows + setup FTS5
├── scripts/                  ← Scripts de actualización manual
├── docs/                     ← Documentación para instalador y abogado
└── data/scjn_tesis.db        ← Base de datos (NO va en git)
```
