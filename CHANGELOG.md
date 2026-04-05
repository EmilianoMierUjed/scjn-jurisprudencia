# Changelog

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
