# SCJN Jurisprudencia Tool vs Semanario Judicial de la Federación

Comparación honesta entre la herramienta y el buscador oficial
[sjf2.scjn.gob.mx](https://sjf2.scjn.gob.mx).

> El SJF oficial es gratuito y siempre tiene la última palabra. Esta
> herramienta no lo reemplaza para todo: lo complementa para los flujos
> donde el SJF se queda corto.

## Tabla resumen

| | SJF2 oficial | SCJN Jurisprudencia Tool |
|---|---|---|
| **Costo del software** | Gratis | Licencia + costo del LLM elegido |
| **Tamaño de la BD** | Online, 311k+ criterios | Local, 311k criterios |
| **Disponibilidad** | Requiere internet, ocasionalmente caído | Offline, 100% local |
| **Tipo de búsqueda** | Por palabra clave | Conceptual con sinónimos (OR), AND de 2-3 conceptos, NEAR por proximidad |
| **Ranking** | Cronológico (más reciente primero) | **Por fuerza vinculante** (Pleno SCJN > Salas > Plenos Regionales > Plenos de Circuito > TCC) + relevancia BM25 dentro de cada bucket + año DESC |
| **Filtro por instancia** | Sí, dropdown manual | Presets jerárquicos (`scjn`, `pleno_scjn`, `salas_scjn`, `primera_sala`, `segunda_sala`, `plenos_regionales`, `plenos_circuito`, `tcc`) |
| **Filtro por época** | Sí, exacto | Acepta variantes (`"decima"`, `"10"`, `"Décima Época"`) |
| **Cruce de conceptos** | No (una sola caja de búsqueda) | Sí, hasta 3 conceptos en AND, cada uno con sinónimos OR adentro |
| **Búsqueda por proximidad** | No | Sí (`buscar_proximidad`, NEAR de FTS5) |
| **Filtro por circuito obligatorio** | No | `buscar_obligatorios_para_circuito` filtra el universo de criterios obligatorios para el 17º (o el que toque) |
| **Línea jurisprudencial cronológica** | Hay que reconstruirla manual | `compilar_linea_jurisprudencial` la devuelve agrupada por época |
| **Cita oficial lista para pegar** | Hay que copiar campo por campo | `extraer_cita_oficial` devuelve el formato canónico del Manual de Estilo del SJF |
| **Análisis del caso** | No (es un buscador) | Protocolo de 5 rondas + clasificación S/A/B/C/D/E/F |
| **Snippet con resaltado** | No | `snippet()` de FTS5 destaca el match en cada resultado |
| **Lectura batch** | No (clic por clic) | `leer_varias_tesis` lee hasta 15 tesis en una llamada |
| **Sincronización con la API** | Es la fuente | Updater incremental cada lunes 6:00 AM |

## Casos de uso donde el SJF se queda corto

**1. "Necesito todas las jurisprudencias del 17º Circuito sobre amparo
indirecto contra orden de aprehensión."**

- SJF: dropdown de instancia → "Tribunales Colegiados de Circuito" →
  buscar "amparo indirecto orden aprehensión" → 200 resultados sin filtro
  por circuito → leer uno por uno y descartar los que no son del 17º.
- Esta herramienta: una llamada a `buscar_obligatorios_para_circuito(17,
  ["amparo indirecto", "orden de aprehensión"])` y obtienes solo lo que
  el TCC de Durango debe aplicar, ya ordenado por fuerza vinculante.

**2. "Cómo evolucionó el criterio de la SCJN sobre el interés superior
del menor en los últimos 10 años."**

- SJF: buscar el término, filtrar por época, ordenar por año, leer una
  por una.
- Esta herramienta: `compilar_linea_jurisprudencial(["interés superior
  del menor", "interés del niño"], anio_minimo=2015)` → cronología
  agrupada por época, en formato compacto, en una sola llamada.

**3. "Tesis donde el ISSSTE y la pensión por viudez aparezcan razonando
juntos, no solo mencionados."**

- SJF: buscar "ISSSTE pensión viudez" → 800 resultados, muchos solo
  mencionan ambos términos por separado.
- Esta herramienta: `buscar_proximidad("issste", "pension viudez",
  distancia=10)` → solo tesis donde ambos términos aparecen a 10 tokens
  o menos, lo que casi garantiza que están razonando sobre la relación.

**4. "Quiero la cita lista para pegar en mi escrito."**

- SJF: copiar campo por campo (rubro, código, fuente, época, libro,
  página, registro), formatear a mano.
- Esta herramienta: `extraer_cita_oficial(id_tesis)` devuelve la cita ya
  formateada según el Manual de Estilo del SJF.

## Donde el SJF sigue siendo mejor

- **Costo cero**: no requiere licencia ni LLM.
- **Última fuente**: si la BD local lleva 5 días sin actualizar y hay
  un criterio nuevo, lo verás antes en el SJF.
- **PDFs originales**: el SJF sirve los PDFs oficiales de la sentencia
  completa. Esta herramienta solo guarda el texto del criterio.
- **Búsqueda histórica por libros y tomos**: el SJF te deja navegar la
  estructura de los libros del Semanario; la herramienta indexa por
  contenido, no por estructura editorial.

## Resumen honesto

El SJF es la fuente y siempre lo va a ser. Esta herramienta es para los
flujos en los que el SJF te obliga a hacer trabajo manual repetitivo
(leer 30 tesis, filtrar a mano, copiar citas) y donde unos minutos de
ahorro por consulta se acumulan rápido en un despacho activo.
