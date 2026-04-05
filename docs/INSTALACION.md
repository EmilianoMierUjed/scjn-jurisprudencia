# Guia de Instalacion para el Instalador

Esta guia es para Emiliano (el instalador), no para el abogado.

## Requisitos en la maquina del cliente

- Windows 10 u 11
- Python 3.10+ (con "Add Python to PATH" marcado al instalar)
- Claude Desktop instalado + suscripcion Claude Pro ($20 USD/mes)
- ~2 GB de espacio en disco

## Preparacion (en tu maquina)

1. Asegurate de que la BD (`scjn_tesis.db`) tenga FTS5 pre-construido.
   Si no, ejecuta:
   ```
   python install/setup_fts.py data/scjn_tesis.db
   ```
   Esto tarda 2-5 minutos pero solo se hace una vez.

2. Copia toda la carpeta del proyecto a un USB.
   La BD va en la subcarpeta `data/`.

## Instalacion en la maquina del cliente

### Paso 1: Copiar archivos
Copia toda la carpeta del USB a `C:\scjn-tool\`.
La estructura debe quedar:
```
C:\scjn-tool\
├── server\server.py
├── updater\actualizar_bd.py
├── install\instalar.bat
├── scripts\actualizar_scjn.bat
├── data\scjn_tesis.db        ← la BD aqui
└── ...
```

### Paso 2: Ejecutar el instalador
Doble clic en `C:\scjn-tool\install\instalar.bat`.

El instalador hace todo automaticamente:
- Verifica Python 3.10+
- Detecta la ruta absoluta de python.exe
- Instala dependencias (mcp, requests)
- Construye FTS5 (si no esta pre-construido, tarda 2-5 min)
- Escribe la config de Claude Desktop con ruta absoluta de python.exe
- Si ya hay config existente, hace merge (no borra otros MCPs)
- Programa actualizacion semanal (Task Scheduler, lunes 6:00 AM)

### Paso 3: Reiniciar Claude Desktop
El abogado debe cerrar Claude Desktop COMPLETAMENTE:
- Clic derecho en el icono de la bandeja del sistema → Quit/Salir
- NO solo cerrar la ventana (eso lo deja corriendo en segundo plano)
- Abrir Claude Desktop de nuevo

### Paso 4: Verificar
En Claude Desktop, el abogado abre una conversacion nueva y pregunta:
```
¿Cuantos criterios tiene la base de datos?
```
Debe responder con ~311,000 criterios y mostrar estadisticas.

## Troubleshooting

### "El MCP no aparece"
1. Verificar que python esta en PATH: `python --version` en cmd
2. Verificar config: abrir `%APPDATA%\Claude\claude_desktop_config.json`
3. Verificar que la ruta a python.exe en el config es ABSOLUTA y CORRECTA
4. Reiniciar Claude Desktop completamente (Quit desde bandeja)

### "Las busquedas son lentas"
El indice FTS5 no esta construido. Ejecutar:
```
python C:\scjn-tool\install\setup_fts.py "C:\scjn-tool\data\scjn_tesis.db"
```

### "Error: No se encontro la base de datos"
Verificar que `scjn_tesis.db` esta en `C:\scjn-tool\data\`

### "La actualizacion automatica no funciona"
- La PC debe estar encendida el lunes a las 6:00 AM
- Verificar en Task Scheduler (buscar "SCJN_Actualizar_BD")
- Ejecutar manualmente: doble clic en `scripts\actualizar_scjn.bat`

## Actualizacion del software

Cuando publiques una nueva version:
1. Reemplaza los archivos en `C:\scjn-tool\` (excepto `data/`)
2. El abogado reinicia Claude Desktop
3. Listo — la BD no se toca, el updater sigue funcionando
