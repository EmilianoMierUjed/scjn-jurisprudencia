# Changelog

## [1.2.0] - 2026-04-07

### Reposicionamiento del producto
- El producto ya no se vende como "herramienta para Claude Desktop". Ahora
  se vende como una **base de datos curada + motor de búsqueda jurídicamente
  especializado**, donde el LLM (Claude o cualquier otro con tool use) es
  una pieza intercambiable. Ver `docs/MODELOS_DE_USO.md`,
  `docs/COMPARACION_VS_SJF.md` y `docs/FAQ_VENTA.md`.

### Refactor arquitectónico — `scjn_core/`
- `server/server.py` pasó de 1,381 → ~600 líneas. Toda la lógica de búsqueda
  ahora vive en el paquete `scjn_core/` (10 módulos: `config`, `database`,
  `errores`, `filters`, `format`, `fts`, `protocol`, `ranking`, `search`,
  `tools_v12`).
- Las funciones de búsqueda son **puras**: reciben la conexión SQLite como
  primer argumento. Esto hace posible reusarlas desde el CLI y testearlas
  sin levantar el MCP.
- Verificación byte-a-byte con `scripts/baseline_v1_1.py` — el output del
  refactor es idéntico al de v1.1 sobre 9 queries representativas.

### CLI standalone (modo API Anthropic) — `cli/scjn_cli.py`
- Nueva alternativa a Claude Desktop. Acepta un caso por archivo o stdin
  y devuelve un reporte usando el mismo protocolo de 5 rondas y las mismas
  13 tools. Pago por uso (~$0.50-3 USD por consulta compleja según modelo).
- Modelos soportados: `claude-sonnet-4-6` (default), `claude-opus-4-6`
  (mejor razonamiento), `claude-haiku-4-5` (más barato).
- Imprime estadísticas de uso (turnos, tools llamadas, tokens) al final
  de cada consulta.
- Rompe la dependencia "obligatoria" de Claude Pro: el cliente puede pagar
  $20/mes a Anthropic O pagar por uso, según le convenga.

### Nuevas tools v1.2 (3) — total ahora 13
- `extraer_cita_oficial(identificador, campo)` — devuelve la cita formal
  lista para pegar en escritos legales mexicanos, en el formato canónico
  del Manual de Estilo del SJF (tipo, código, fuente, época, mes, año,
  registro digital).
- `compilar_linea_jurisprudencial(tema, anio_minimo, instancia, limite)`
  — cronología de jurisprudencias sobre un tema, agrupada por época.
  Útil para argumentar la evolución de un criterio.
- `buscar_obligatorios_para_circuito(circuito, terminos, limite)` — filtra
  el universo de criterios obligatorios para un circuito específico
  (Pleno SCJN + Salas SCJN + Plenos Regionales + Plenos del Circuito + TCC
  del Circuito). Acepta el circuito como número (17), romano ("XVII") u
  ordinal castellano ("decimo septimo"). Caso de uso real: abogado en
  Durango (17º Circuito) que solo quiere ver lo que su tribunal está
  obligado a aplicar.

### Reducción de tamaño de la BD
- Eliminada la columna `json_completo`, que ocupaba ~612 MB y nunca se
  leía en runtime. **BD pasó de 1.7 GB → 989 MB (-43%)**, lo que mejora
  distribución por USB/Drive y velocidad de FTS5 en cache.
- `scripts/eliminar_json_completo.py` automatiza el ALTER + VACUUM con
  backup previo.
- `updater/actualizar_bd.py` ya no inserta `json_completo` en sus
  INSERT OR REPLACE.

### Errores humanizados
- Todas las funciones de `scjn_core` ahora wrappean excepciones por
  `errores.humanizar(exc, contexto)`, que mapea los errores típicos de
  SQLite/FTS5 a mensajes accionables ("términos con caracteres especiales",
  "BD bloqueada por otro proceso", etc.) en lugar de stack traces crudos.

### Tests con pytest (51 → 82 tests, todos en verde)
- `tests/test_ranking.py` — TestNivelVinculante (8) + TestRegresionBugV10
  (4) que protegen contra que vuelva a aparecer el bug de v1.0 (Pleno SCJN
  apareciendo después de TCC).
- `tests/test_filters.py` — TestNormalizarEpoca (15 parametrize),
  TestFiltroEpocaEnBD (3), TestInstanciaPresets (3).
- `tests/test_search.py` — smoke tests para las 10 funciones de búsqueda.
- `tests/test_tools_v12.py` — TestParseCircuito (14 válidos + 7 inválidos),
  TestExtraerCitaOficial, TestLineaJurisprudencial, TestObligatoriosCircuito.
- `tests/conftest.py` — fixture session-scoped que abre la BD real
  read-only.

### Distribución
- `install/scjn_mcp_server.spec` y `install/scjn_cli.spec` — specs de
  PyInstaller para compilar `scjn-mcp-server.exe` y `scjn-cli.exe`. El
  cliente ya no necesita instalar Python ni configurar PYTHONPATH.
- `install/instalar_exe.bat` — instalador alternativo para clientes que
  reciben los `.exe`. Mantiene el `instalar.bat` clásico para los que
  prefieren Python.

### Validación de la BD
- `scripts/validar_bd.py` — healthcheck con 11 checks: integrity_check,
  foreign_key_check, schema mínimo, FTS5 integrity-check, drift entre
  `tesis` y `tesis_fts`, triggers de sincronización, sanity check de
  búsqueda. Sale con código 1 si algún check falla.
- `scripts/baseline_v1_1.py` — script de regresión que ejecuta 9 queries
  representativas y diff'ea el output entre el wrapper viejo y el refactor.

### Mejoras del protocolo
- Las instrucciones del protocolo de 5 rondas se movieron a
  `scjn_core/protocol.py` para que el MCP server y el CLI las compartan
  byte a byte.

## [1.1.0] - 2026-04-07

### Fixes críticos
- **Orden por fuerza vinculante arreglado**: la versión anterior miraba solo
  el campo `instancia`, pero en la BD las 205k tesis de SCJN comparten
  `instancia="Suprema Corte de Justicia de la Nación"`. El desglose real
  Pleno/Salas vive en `organo_juris`. Resultado del bug: las tesis de Pleno
  SCJN y Salas aparecían al final, después de TCC. Ahora el orden reconoce
  correctamente Pleno SCJN > Salas > Plenos Regionales > Plenos de Circuito
  > TCC, y añade BM25 como criterio de desempate dentro de cada bucket.
- **Filtro de época**: antes usaba `LIKE` sobre texto con acentos, lo que
  fallaba si el usuario pasaba "Decima" en vez de "Décima". Ahora se
  normaliza y acepta "decima", "10", "Décima Época", "undecima", etc.

### Nuevas features de búsqueda (igualan y superan al SJF2)
- **BM25 ranking**: los resultados se ordenan por relevancia dentro de
  cada bucket de fuerza vinculante.
- **Snippet con resaltado**: cada resultado incluye el fragmento relevante
  del texto con el match destacado (`«match»`), usando `snippet()` de FTS5.
  Antes mostraba los primeros 600 caracteres del texto, que muchas veces
  no tenían nada que ver con la búsqueda.
- **Filtros nuevos** en `buscar_jurisprudencia` y `buscar_interseccion`:
  `materia`, `instancia` (presets: scjn, pleno_scjn, salas_scjn, primera_sala,
  segunda_sala, plenos_regionales, plenos_circuito, tcc), `organo`,
  `anio_maximo`, `epocas` (lista), `buscar_en` (todo/rubro/texto), `orden`
  (vinculancia/relevancia/reciente).
- **3 conceptos en `buscar_interseccion`**: ahora acepta `concepto_c` opcional
  para cruces de 3 conceptos (A AND B AND C).

### Nuevas herramientas MCP
- `buscar_proximidad(termino_a, termino_b, distancia)` — búsqueda por
  proximidad NEAR() de FTS5. Encuentra tesis donde dos conceptos aparecen
  dentro de N tokens, lo que implica que razonan sobre la relación entre
  ambos (no solo que los mencionan por separado).
- `buscar_rubro(terminos)` — búsqueda restringida al rubro. Más preciso
  cuando el abogado recuerda parte del título o quiere ver criterios bajo
  un tema específico.
- `leer_varias_tesis(identificadores)` — lee hasta 15 tesis en una sola
  llamada. Evita N ida-y-vueltas durante la Ronda 3 del protocolo.
- `buscar_similares(id_tesis)` — dada una tesis, encuentra otras con
  rubros similares usando ranking BM25. Ideal para reconstruir la línea
  jurisprudencial completa de un tema.

### Mejoras
- `buscar_contradiccion` ahora busca también en `precedentes` y `rubro`,
  no solo en `texto`.
- `format_resultados` ahora calcula y muestra el nivel (S/A/B/C/D/E/F) de
  cada tesis. Claude tiene la clasificación pre-hecha, no necesita inferirla.
- `format_resultados` ahora incluye `organo_juris` y `fuente`.
- `leer_tesis_completa` y `leer_varias_tesis` truncan textos y precedentes
  muy largos para evitar explosión de tokens.
- `info_base_datos` ahora muestra desglose por instancia (fuerza vinculante)
  y por época.
- `explorar_valores` acepta el campo `fuente`.
- Instrucciones del protocolo actualizadas con niveles S-F correctos,
  épocas actualizadas (Undécima y Duodécima), y sección "Hints de búsqueda"
  explicando cuándo usar cada filtro.

## [1.0.0] - 2026-04-04

### Primera version comercial

- MCP Server con 6 herramientas de busqueda (buscar_jurisprudencia,
  buscar_interseccion, leer_tesis_completa, buscar_contradiccion,
  explorar_valores, info_base_datos)
- Base de datos con ~311,000 criterios SCJN (1911-2026) con indice FTS5
- Protocolo de busqueda estrategica integrado en instrucciones del MCP
  (5 rondas obligatorias, clasificacion por fuerza vinculante, presentacion
  estrategica con criterios de riesgo)
- Instalador automatizado para Windows (instalar.bat) con deteccion de
  ruta absoluta de python.exe y merge de configuracion
- Actualizador incremental desde API SCJN con Task Scheduler
- Documentacion para instalador y usuario final
- DB_PATH configurable por variable de entorno con fallback relativo
