# Contexto del Proyecto — SCJN Jurisprudencia Tool

Documento de referencia para trabajar el proyecto en cualquier sesion de chat.
Pega este documento al inicio de una conversacion nueva con Claude para darle
contexto completo del proyecto.

---

## Que es este proyecto

Es un producto comercial de busqueda de jurisprudencia de la SCJN orientado a
despachos juridicos en Mexico. El producto consiste en:

1. **Base de datos SQLite** con ~311,000 criterios judiciales (tesis aisladas y
   jurisprudencias, 1911-2026), indexada con FTS5 para busquedas rapidas
2. **MCP Server** (Model Context Protocol) en Python que conecta Claude Desktop
   con la base de datos, exponiendo 6 herramientas de busqueda
3. **Protocolo de busqueda estrategica** embebido en las instrucciones del MCP
   que guia a Claude para razonar como abogado litigante (5 rondas, clasificacion
   por fuerza vinculante, presentacion estrategica con criterios adversos)
4. **Instalador automatizado** para Windows (instalar.bat)
5. **Actualizador incremental** que descarga tesis nuevas de la API publica de la SCJN

## Arquitectura actual (v1.0.0, 2026-04-04)

```
Base_Datos_SCJN/                    ← directorio raiz del producto
├── server/
│   ├── server.py                   ← MCP server (FastMCP, 6 tools)
│   │                                  Contiene INSTRUCCIONES (~2,000 palabras)
│   │                                  con el protocolo completo de busqueda.
│   │                                  DB_PATH configurable por env var, default
│   │                                  relativo a ../data/scjn_tesis.db
│   └── requirements.txt            ← mcp>=1.2.0
├── updater/
│   ├── actualizar_bd.py            ← descarga incremental desde API SCJN
│   └── requirements.txt            ← requests>=2.28.0
├── install/
│   ├── instalar.bat                ← instalador Windows (6 fases):
│   │                                  1. Verifica Python 3.10+
│   │                                  2. Verifica BD en data/
│   │                                  3. pip install dependencias
│   │                                  4. Construye FTS5 (si no existe)
│   │                                  5. Escribe config Claude Desktop
│   │                                     con ruta absoluta de python.exe
│   │                                     y merge con config existente
│   │                                  6. Task Scheduler (lunes 6AM)
│   ├── setup_fts.py                ← constructor de indices FTS5
│   └── claude_desktop_config.json  ← template (el instalador lo modifica)
├── scripts/
│   ├── actualizar_scjn.bat         ← actualizacion manual Windows
│   └── actualizar_scjn.sh          ← actualizacion manual Linux/cron
├── docs/
│   ├── INSTALACION.md              ← guia para el instalador (Emiliano)
│   ├── USO_ABOGADO.md              ← guia para el usuario final
│   └── CONTEXTO_PROYECTO.md        ← este archivo
├── data/
│   └── scjn_tesis.db               ← BD (1.7 GB, NO va en git)
├── .claude/
│   └── settings.local.json         ← permisos de Claude Code para este proyecto
├── CLAUDE.md                       ← schema de la BD + como buscar con FTS5
├── README.md                       ← overview del producto
├── VERSION                         ← "1.0.0"
├── CHANGELOG.md                    ← historial de cambios
├── LICENSE.md                      ← licencia propietaria
└── .gitignore
```

## Decisiones de diseno clave

### 1. Donde vive la metodologia de busqueda

**En el MCP (server.py, parametro `instructions` de FastMCP).**

Razon: El MCP es el unico componente que llega a Claude Desktop (Windows,
target comercial) Y a Claude Code (Linux, desarrollo). Claude Desktop NO
tiene sistema de skills/commands. Si la metodologia estuviera solo en un
skill, no funcionaria para los clientes.

El skill de Claude Code (`~/.claude/commands/jurisprudencia.md`) es un
wrapper ligero que solo agrega "lee el expediente del workspace primero"
— algo que el MCP no puede hacer.

### 2. Donde vive la BD

La BD (1.7 GB) NO va en git. Se distribuye por USB a clientes locales
(Durango) o por descarga (Google Drive / GitHub Releases) a remotos.

El `DB_PATH` se configura por variable de entorno en `claude_desktop_config.json`.
El default en server.py es relativo: `../data/scjn_tesis.db` (funciona en
Linux sin configuracion adicional).

### 3. No hay proyecto en Claude Desktop

Antes, el flujo de instalacion requeria que el cliente creara un "Proyecto" en
Claude Desktop y pegara las instrucciones manualmente. Esto se elimino: las
instrucciones van en el MCP y se inyectan automaticamente.

### 4. Ruta absoluta de python.exe

Claude Desktop en Windows NO hereda el PATH del sistema. El instalador
detecta la ruta absoluta de python.exe con `where python` y la escribe
en la config. Sin esto, Claude Desktop no puede lanzar el MCP server.

## Tools del MCP (las 6 herramientas)

| Tool | Proposito | Parametros clave |
|------|-----------|------------------|
| buscar_jurisprudencia | Busqueda conceptual OR | terminos: list[str], solo_jurisprudencia, anio_minimo |
| buscar_interseccion | Cruce de 2 conceptos AND | concepto_a: list[str], concepto_b: list[str] |
| leer_tesis_completa | Texto completo de una tesis | identificador, campo: "id_tesis"/"tesis_codigo"/"rubro" |
| buscar_contradiccion | Jurisprudencia por contradiccion | terminos: list[str] |
| explorar_valores | Valores unicos de un campo | campo: "tipo_tesis"/"epoca"/"instancia"/etc. |
| info_base_datos | Estadisticas de la BD | (sin parametros) |

## Schema de la BD (tabla `tesis`)

| Columna | Tipo | Uso |
|---------|------|-----|
| id_tesis | TEXT PK | Identificador unico |
| rubro | TEXT | Titulo/encabezado |
| epoca | TEXT | Epoca del Semanario Judicial |
| instancia | TEXT | Organo emisor (Pleno, Salas, TCC...) |
| organo_juris | TEXT | Organo especifico |
| tipo_tesis | TEXT | "Aislada" o "Jurisprudencia" |
| anio | INTEGER | Anio de publicacion |
| materias | TEXT | Materias separadas por coma |
| tesis_codigo | TEXT | Codigo para cita formal |
| texto | TEXT | Texto completo (~1000 chars promedio) |
| precedentes | TEXT | Casos originarios |
| json_completo | TEXT | JSON original de la API |

Tabla FTS5: `tesis_fts` (indice sobre rubro, texto, precedentes, materias).
Tokenizer: unicode61 remove_diacritics 2 (ignora acentos).

## API de la SCJN (para el actualizador)

- Base: `https://bicentenario.scjn.gob.mx/repositorio-scjn`
- Endpoints:
  - `/api/v1/tesis/count` — total de tesis
  - `/api/v1/tesis/ids?page=N` — IDs paginados
  - `/api/v1/tesis/{id_tesis}` — detalle de una tesis
- Sin autenticacion requerida
- No soporta filtro por fecha (siempre recorre todo)

## Entornos

| Aspecto | Linux (desarrollo) | Windows (produccion) |
|---------|-------------------|---------------------|
| Ruta BD | Relativa (../data/) | C:\scjn-tool\data\ via env |
| Metodologia | MCP instructions (identicas) | MCP instructions (identicas) |
| Skill extra | ~/.claude/commands/jurisprudencia.md | No existe, no se necesita |
| Actualizacion | scripts/actualizar_scjn.sh | Task Scheduler + .bat |
| Config Claude | ~/.claude/.mcp.json | %APPDATA%\Claude\claude_desktop_config.json |

## Configuracion en Linux (Claude Code)

Archivo `~/.claude/.mcp.json`:
```json
{
  "mcpServers": {
    "scjn-jurisprudencia": {
      "command": "/usr/bin/python3",
      "args": ["/ruta/al/server/server.py"],
      "env": {
        "DB_PATH": "/ruta/a/scjn_tesis.db"
      }
    }
  }
}
```

## Modelo de negocio

- Target: despachos juridicos en Mexico (primero Durango, luego nacional)
- Requisito del cliente: suscripcion Claude Pro ($20 USD/mes a Anthropic)
- Instalacion: presencial (USB) o remota
- Actualizaciones de la BD: automaticas (Task Scheduler)
- Actualizaciones del software: manuales (reemplazar archivos, reiniciar)

## Historial de decisiones

- **2026-03-25:** Sistema creado con skill YAML + MCP con instrucciones completas
- **2026-03-30:** Diagnosticado que el skill estaba muerto (formato incorrecto,
  tools de Claude Desktop, ruta equivocada). Instalado en ~/.claude/commands/
- **2026-04-03:** Auditoría completa. Detectada triple redundancia de instrucciones.
  Skill simplificado, MCP simplificado.
- **2026-04-04:** Rediseño para comercializacion. Metodologia restaurada en MCP
  (unico componente que llega a Claude Desktop). Skill reducido a wrapper.
  Instalador mejorado con ruta absoluta de python.exe y merge de config.
  Documentacion reorganizada. Git inicializado. v1.0.0.

## Pendientes futuros (no para v1)

- Crear instalador .exe/.msi (para eliminar dependencia de python en PATH)
- Auto-updater del software (no solo de la BD)
- API REST como alternativa al MCP (para clientes sin Claude Desktop)
- Soporte para otros LLMs (opcional, largo plazo)
- Dashboard web de uso/estadisticas (para monitoreo de clientes)
