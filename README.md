# SCJN Jurisprudencia Tool

**Base de datos curada de 311,000 criterios de la SCJN (1911-2026) con
motor de búsqueda jurídicamente especializado.** Diseñada por y para
abogados litigantes mexicanos.

El producto es la BD + el motor + el protocolo de búsqueda. El LLM
(Claude Desktop, API Anthropic, próximamente otros) es una pieza
intercambiable que opera sobre ese motor.

## Qué resuelve

El SJF oficial busca por palabras clave y ordena cronológicamente.
Encontrar un criterio aplicable a tu caso requiere abrir 30 tabs y
leerlas una por una.

Esta herramienta:

- Acepta **conceptos** con sinónimos, no palabras sueltas. Una búsqueda
  por "interés superior del menor" automáticamente cubre "interés del
  niño", "principio del interés del menor", etc.
- Ordena **por fuerza vinculante** (Pleno SCJN → Salas → Plenos
  Regionales → Plenos de Circuito → TCC), no por fecha. El primer
  resultado siempre es el que el tribunal está obligado a aplicar.
- Cruza **2-3 conceptos a la vez** (AND con sinónimos OR adentro) para
  encontrar tesis que razonen sobre la *relación* entre los conceptos,
  no solo que los mencionen por separado.
- Aplica un **protocolo de 5 rondas** que obliga al LLM a buscar de
  forma estratégica antes de responder, en lugar de soltar la primera
  tesis que se le ocurra.

## Modos de uso

| Modo | LLM | Costo | Recomendado para |
|------|-----|-------|-------------------|
| **Claude Desktop + MCP** | Claude Pro ($20 USD/mes) | Suscripción ilimitada | Uso diario, conversación |
| **CLI standalone (API)** | API Anthropic (pago por uso) | ~$0.50–3 USD por consulta | Uso ocasional, automatizaciones, batch |
| **Solo SQL** | Ninguno | Gratis | Despachos con dev interno |

Ver [`docs/MODELOS_DE_USO.md`](docs/MODELOS_DE_USO.md) para los detalles
de cada modo y el cálculo de costo.

## Tools del motor (13)

| Tool | Para qué |
|------|----------|
| `buscar_jurisprudencia` | Búsqueda por concepto con sinónimos + filtros (materia, instancia, época, año, etc.) |
| `buscar_interseccion` | Cruza 2-3 conceptos (A AND B [AND C]) |
| `buscar_proximidad` | NEAR: dos términos a N tokens de distancia |
| `buscar_rubro` | Búsqueda restringida al título de la tesis |
| `buscar_similares` | Dada una tesis, encuentra otras con tema similar (BM25) |
| `buscar_contradiccion` | Jurisprudencia surgida de contradicción de tesis |
| `buscar_obligatorios_para_circuito` | Filtra criterios obligatorios para un circuito específico (1-32) |
| `compilar_linea_jurisprudencial` | Cronología de un tema agrupada por época |
| `extraer_cita_oficial` | Cita formal lista para pegar en escritos legales |
| `leer_tesis_completa` | Texto completo + metadatos de una tesis |
| `leer_varias_tesis` | Hasta 15 tesis en una sola llamada (batch) |
| `explorar_valores` | Valores únicos de un campo (instancia, época, materias…) |
| `info_base_datos` | Estadísticas y estado de la BD |

## Estructura del proyecto

```
Base_Datos_SCJN/
├── scjn_core/                ← Núcleo: lógica pura de búsqueda
│   ├── search.py             ← 10 funciones de búsqueda
│   ├── tools_v12.py          ← 3 tools nuevas (cita, línea, circuito)
│   ├── protocol.py           ← Protocolo de 5 rondas (instrucciones LLM)
│   ├── ranking.py            ← Orden por fuerza vinculante (S/A/B/C/D/E/F)
│   ├── filters.py            ← Presets de instancia, normalización de épocas
│   ├── fts.py                ← Sanitización de queries FTS5
│   ├── format.py             ← Formato de resultados con snippet
│   ├── errores.py            ← Errores humanizados
│   ├── database.py           ← Conexión SQLite
│   └── config.py             ← Rutas y constantes
├── server/server.py          ← Wrapper MCP delgado (Claude Desktop)
├── cli/scjn_cli.py           ← CLI standalone (API Anthropic)
├── updater/                  ← Actualizador semanal desde API SCJN
├── install/                  ← Instaladores Windows + specs PyInstaller
├── scripts/                  ← Validación, baseline, mantenimiento
├── tests/                    ← 82 tests de pytest
├── docs/                     ← Documentación técnica + de venta
└── data/scjn_tesis.db        ← Base de datos (~990 MB, no va en git)
```

## Diferenciadores frente al SJF oficial

Ver [`docs/COMPARACION_VS_SJF.md`](docs/COMPARACION_VS_SJF.md) para la
tabla completa. Resumen:

- **Búsqueda conceptual con sinónimos** vs búsqueda por palabra clave
- **Ranking por fuerza vinculante** vs cronológico
- **Funciona offline** vs requiere internet
- **Análisis del caso con protocolo de 5 rondas** vs nada
- **Cita oficial pre-formateada** vs copy-paste manual

## Descarga inicial de la base de datos

La BD (~990 MB, ~311,000 criterios) no está en este repo. Para obtenerla
tienes dos opciones:

### Opción A — Descargar desde la API SCJN (gratis, tarda ~4-6 horas)

```bash
# Instalar dependencia
pip install requests

# Correr el script desde la raíz del repo
python updater/actualizar_bd.py
```

El script crea automáticamente `data/scjn_tesis.db` con el esquema correcto
(tabla, índice FTS5, triggers) y descarga todos los criterios de la API pública
del Semanario Judicial. No requiere ningún archivo previo ni credenciales.

**Para actualizaciones incrementales** (tesis nuevas solamente), corre el mismo
comando — el script detecta qué IDs ya tienes y sólo baja los nuevos.

### Opción B — Recibir la BD pre-construida

Si recibes el producto como cliente, la BD viene en USB o descarga directa.
Colócala en `data/scjn_tesis.db` y pasa directamente a Instalación.

---

## Instalación rápida (cliente Windows)

1. Copiar la carpeta a `C:\scjn-tool\`
2. Copiar `scjn_tesis.db` a `C:\scjn-tool\data\`
3. Doble clic en `install\instalar.bat` (o `instalar_exe.bat` si recibiste
   los `.exe` precompilados)
4. Reiniciar Claude Desktop

Ver [`docs/INSTALACION.md`](docs/INSTALACION.md) para la guía completa.

## Mantenimiento

- **Actualización automática**: Task Scheduler de Windows cada lunes 6:00 AM
- **Actualización manual**: `scripts\actualizar_scjn.bat`
- **Healthcheck**: `python scripts/validar_bd.py` — verifica integridad,
  drift FTS y triggers de sincronización
- **Tests**: `pytest tests/ -v` (82 tests)

## Requisitos

- Windows 10/11 (cliente) o Linux (desarrollo)
- Python 3.10+ (innecesario si usas los `.exe` compilados)
- Para Claude Desktop: suscripción Claude Pro
- Para el CLI: una API key de Anthropic
- ~1.5 GB libres en disco (BD + dependencias)

## Preguntas frecuentes de venta

- *"¿Esto es Claude haciendo el trabajo?"*
- *"¿Puedo usarlo sin pagar Claude Pro?"*
- *"¿Qué pasa si Anthropic cierra mañana?"*

→ Respuestas honestas en [`docs/FAQ_VENTA.md`](docs/FAQ_VENTA.md).
