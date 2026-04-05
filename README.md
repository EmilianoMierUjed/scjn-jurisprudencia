# SCJN Jurisprudencia Tool

Herramienta de busqueda inteligente de jurisprudencia de la SCJN para
Claude Desktop. Base de datos local con ~311,000 criterios (tesis y
jurisprudencias, 1911-2026) consultable mediante lenguaje natural.

## Estructura del proyecto

```
scjn-tool/
├── server/
│   ├── server.py              ← MCP server (puente Claude - SQLite)
│   └── requirements.txt
├── updater/
│   ├── actualizar_bd.py       ← Descarga tesis nuevas de la API SCJN
│   └── requirements.txt
├── install/
│   ├── instalar.bat           ← Instalador automatizado
│   ├── setup_fts.py           ← Construye indice de busqueda rapida
│   └── claude_desktop_config.json  ← Template de configuracion
├── scripts/
│   ├── actualizar_scjn.bat    ← Actualizacion manual Windows
│   └── actualizar_scjn.sh     ← Actualizacion manual Linux
├── docs/
│   ├── INSTALACION.md         ← Guia para el instalador
│   └── USO_ABOGADO.md         ← Guia para el usuario final
├── data/
│   └── scjn_tesis.db          ← Base de datos (NO va en git)
├── CLAUDE.md                  ← Documentacion tecnica (schema BD)
├── VERSION                    ← Version actual del producto
├── CHANGELOG.md               ← Historial de cambios
└── LICENSE.md                 ← Licencia de uso
```

## Requisitos

- Windows 10/11 (para clientes) o Linux (para desarrollo)
- Python 3.10+
- Claude Desktop + suscripcion Claude Pro
- ~2 GB de espacio en disco

## Instalacion rapida

1. Copiar toda la carpeta a `C:\scjn-tool\`
2. Copiar `scjn_tesis.db` a `C:\scjn-tool\data\`
3. Doble clic en `C:\scjn-tool\install\instalar.bat`
4. Reiniciar Claude Desktop

Ver [docs/INSTALACION.md](docs/INSTALACION.md) para la guia completa.

## Herramientas disponibles para Claude

| Tool | Que hace |
|------|----------|
| buscar_jurisprudencia | Busqueda por concepto con sinonimos (OR) |
| buscar_interseccion | Cruza dos conceptos (A AND B) |
| leer_tesis_completa | Lee texto completo de una tesis |
| buscar_contradiccion | Jurisprudencia por contradiccion de tesis |
| explorar_valores | Valores disponibles en campos de la BD |
| info_base_datos | Estadisticas y estado de la BD |

## Mantenimiento

- **Actualizacion automatica:** Task Scheduler, cada lunes 6:00 AM
- **Actualizacion manual:** Doble clic en `scripts\actualizar_scjn.bat`
- **Actualizacion del software:** Reemplazar archivos, reiniciar Claude Desktop
