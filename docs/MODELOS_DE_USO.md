# Modelos de uso

La herramienta es **un motor de búsqueda con una base de datos curada**.
El componente que escribe el reporte final (el LLM) es intercambiable.
Hay tres formas de usarla, según presupuesto y volumen de consultas.

## Modelo 1 — Claude Desktop + Pro (recomendado para uso diario)

**Cómo funciona**: el MCP server (`server/server.py` o
`scjn-mcp-server.exe`) se registra en `claude_desktop_config.json` y
queda disponible como herramienta para Claude Desktop. El abogado
escribe sus casos en la conversación normal de Claude; cuando Claude
necesita buscar jurisprudencia, llama a las 13 tools de la herramienta
de forma transparente.

**Costo**: Claude Pro **$20 USD/mes** (suscripción ilimitada en la
práctica para uso humano normal).

**Ventajas**:
- Mejor experiencia conversacional. Puedes ir afinando el caso a lo
  largo de la conversación, pedir refinamientos, comparar criterios.
- No piensas en costo por consulta — pagas plano y usas todo lo que
  necesites.
- Adjunta documentos (sentencias, expedientes en PDF) directamente en
  el chat de Claude Desktop.

**Desventajas**:
- Requiere instalar Claude Desktop y mantener la sesión iniciada.
- Si Claude Desktop cambia su política de MCPs en el futuro, puede
  romper la integración.

**Para quién**: el abogado promedio que va a usar la herramienta varias
veces por semana. **Es el modo recomendado.**

## Modelo 2 — CLI standalone (API Anthropic, pago por uso)

**Cómo funciona**: el binario `scjn-cli.exe` (o `python cli/scjn_cli.py`)
recibe un caso por archivo o stdin, ejecuta el mismo protocolo de 5
rondas con las mismas 13 tools, y devuelve el reporte por stdout o a un
archivo `.md`.

```
set ANTHROPIC_API_KEY=sk-ant-...
scjn-cli --caso casos\amparo_pension.txt --output reporte.md
```

**Costo**: pago por uso de la API Anthropic. Estimación por consulta
compleja del protocolo de 5 rondas (≈30k tokens entrada, 5k salida):

| Modelo | Costo aproximado por consulta |
|---|---|
| `claude-haiku-4-5` | ~$0.10–0.30 USD |
| `claude-sonnet-4-6` (default) | ~$0.50–1.50 USD |
| `claude-opus-4-6` | ~$2–5 USD |

(Las cifras dependen del precio público de Anthropic al momento de la
consulta. Verificar siempre el costo actual en
[anthropic.com/pricing](https://anthropic.com/pricing).)

**Ventajas**:
- **Sin suscripción**. Si haces 5 consultas al mes, pagas centavos. Si
  haces 200, pagas según volumen real.
- **Automatizable**. Ideal para procesar lotes de expedientes en una
  sola corrida (`for caso in casos/*.txt; do scjn-cli --caso $caso ...`).
- **Independiente de Claude Desktop**. Si no quieres instalarlo o si
  estás en un servidor, esta es la vía.
- **Estadísticas explícitas**: el CLI imprime turnos, tools llamadas y
  tokens al final de cada consulta. Sabes exactamente cuánto te costó.

**Desventajas**:
- No es conversacional — cada invocación es one-shot. Si quieres afinar,
  vuelves a correr.
- Necesitas obtener una API key de Anthropic
  ([console.anthropic.com](https://console.anthropic.com)).
- Para consultas casuales, puede salirte más caro que la suscripción si
  haces muchas al mes.

**Para quién**:
- El abogado que solo necesita la herramienta de vez en cuando.
- El despacho que quiere procesar 50 expedientes en batch.
- El usuario que ya tiene API key de Anthropic para otra cosa.

## Modelo 3 — Solo BD + scripts SQL

**Cómo funciona**: la BD `scjn_tesis.db` es un SQLite estándar. Cualquier
herramienta que hable SQL (DB Browser for SQLite, DBeaver, Python con
sqlite3, lo que sea) puede consultarla directamente.

**Costo**: cero. Una vez que tienes la BD, no pagas nada.

**Ventajas**:
- Cero dependencia de LLMs.
- Velocidad máxima — sin overhead de tool use ni protocolo conversacional.
- Si tienes un dev interno, puedes integrar la BD a tu sistema propio.

**Desventajas**:
- Tienes que saber SQL y FTS5.
- No tienes el protocolo de 5 rondas ni el ranking automático por fuerza
  vinculante (aunque puedes copiarlo de `scjn_core/ranking.py`).
- No tienes los presets de instancia ni la normalización de épocas
  (los puedes copiar de `scjn_core/filters.py`).

**Para quién**: despachos con un desarrollador interno que quieren
construir su propia interfaz, o usuarios power que prefieren queries
exactas a tener un LLM en el medio.

## ¿Cuál elijo?

| Tu situación | Modelo recomendado |
|---|---|
| Soy abogado, voy a usarlo a diario | **1 — Claude Desktop + Pro** |
| Lo uso 2-3 veces al mes | **2 — CLI con API** |
| Tengo despacho con dev interno | **3 — Solo BD** |
| Quiero procesar 100 expedientes en batch | **2 — CLI con API** |
| No quiero pagar nada extra al mes | **2** (pago por uso) o **3** (gratis) |
| Prefiero conversación natural | **1** |
| Estoy en un servidor sin GUI | **2** o **3** |

## Cambiar de modelo

Los tres modelos comparten **la misma BD** y **las mismas 13 tools**.
Puedes empezar con el Modelo 1 y migrar al 2 más adelante sin perder
nada — la BD es tuya y se queda en tu disco.
