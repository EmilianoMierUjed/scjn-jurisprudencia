# Preguntas frecuentes (para el abogado escéptico)

> Documento honesto. No es un folleto: si la respuesta a una pregunta es
> "sí, pero…", se dice "sí, pero…".

---

## Sobre el producto

### "¿Esto es solo Claude haciendo el trabajo?"

**No.** Claude (o el LLM que elijas) es el operador, el que conversa
contigo y arma el reporte final. Lo que tú compras es:

1. **La base de datos curada y validada**: 311,000 criterios de la SCJN
   desde 1911, con todos los campos limpios e indexados con FTS5.
   Construirla y mantenerla sincronizada con la API oficial es trabajo
   recurrente, no se hace solo.
2. **El motor de búsqueda jurídicamente especializado**: las 13 tools no
   son `SELECT * FROM tesis WHERE texto LIKE '%X%'`. Cada una está
   pensada para un flujo legal real (cruce de conceptos, búsqueda por
   proximidad, filtro por circuito obligatorio, cita oficial canónica).
3. **El protocolo de 5 rondas**: las instrucciones que obligan al LLM a
   buscar de forma estratégica antes de responder, en lugar de soltar la
   primera tesis que se le ocurra. Es la diferencia entre Claude
   improvisando y Claude ejecutando una metodología jurídica.
4. **El ranking por fuerza vinculante**: el orden de los resultados
   refleja el Art. 217 de la Ley de Amparo, no la fecha. Esto **es** la
   ventaja sobre el SJF oficial.

Sin la BD curada, sin las tools, sin el protocolo y sin el ranking,
Claude no puede hacer este trabajo. Lo intentamos: Claude solo, sin la
herramienta, inventa criterios y se equivoca de circuito.

### "¿Por qué no uso el SJF oficial directamente? Es gratis."

Lo deberías seguir usando para validar la última versión publicada de
cada tesis. Esta herramienta no lo reemplaza, lo complementa para los
flujos donde el SJF te obliga a hacer trabajo manual: leer 30 tesis para
descartar las que no son del circuito que te toca, copiar la cita campo
por campo, reconstruir la línea jurisprudencial de un tema a mano.

Ver [`COMPARACION_VS_SJF.md`](COMPARACION_VS_SJF.md) para la tabla.

### "¿La base de datos está actualizada?"

Sí, hay un actualizador incremental que corre cada lunes a las 6:00 AM
(Task Scheduler de Windows). Descarga solo lo nuevo desde la API SCJN.

Para forzar una actualización manual: doble clic en
`scripts\actualizar_scjn.bat`.

Si la BD lleva varios días sin actualizarse y necesitas un criterio
nuevísimo, valídalo en el SJF oficial antes de citarlo.

---

## Sobre el costo

### "¿Puedo usarlo sin pagar Claude Pro?"

**Sí.** Hay tres modos de uso:

1. **Claude Desktop + Pro** ($20 USD/mes, ilimitado en la práctica). Es
   el modo más cómodo.
2. **CLI standalone con API Anthropic** (pago por uso, ~$0.50–3 USD por
   consulta compleja). Sin suscripción. Ideal si solo lo usas algunas
   veces al mes.
3. **Solo BD + scripts SQL** (gratis si sabes SQL, o si tienes un dev
   en el despacho).

Ver [`MODELOS_DE_USO.md`](MODELOS_DE_USO.md) para los detalles.

### "¿Cuánto cuesta una consulta con el modo CLI?"

Depende del modelo elegido y de la complejidad del caso:

- Caso sencillo con `claude-haiku-4-5`: ~$0.10–0.30 USD
- Caso complejo con `claude-sonnet-4-6` (default): ~$0.50–1.50 USD
- Caso complejo con `claude-opus-4-6`: ~$2–5 USD

El CLI imprime los tokens y el conteo de turnos al final de cada
consulta, así sabes exactamente cuánto gastaste.

### "¿Qué cuesta la herramienta en sí?"

[A definir según tu modelo de licenciamiento. La herramienta es tuya;
el costo del LLM es aparte.]

---

## Sobre dependencias

### "¿Qué pasa si Anthropic cierra mañana?"

- **La BD es tuya**. Es un archivo `.db` en tu disco. SQLite va a
  funcionar mientras existan las computadoras.
- **Las queries funcionan en cualquier herramienta SQL**. Las tools de
  `scjn_core/search.py` son código Python puro sobre SQLite — no
  dependen de Anthropic.
- **El protocolo se puede portar a cualquier LLM con tool use**.
  Actualmente solo está implementado para Anthropic, pero el formato
  de tool use es esencialmente el mismo en OpenAI, Google, etc.
- Si Anthropic desaparece, lo que pierdes es el "operador" amable que
  conversa contigo. La capacidad de buscar jurisprudencia en tu BD
  con las 13 tools sigue intacta.

### "¿Funciona sin internet?"

**Sí, completamente offline.** La BD es local, las tools corren
localmente, y los binarios `.exe` de PyInstaller no necesitan red.

La única vez que necesitas internet es:
1. Cuando el actualizador semanal descarga tesis nuevas de la API SCJN.
2. Cuando el LLM elegido (Claude o cualquier otro) necesita conectarse
   a su API para razonar sobre tu caso. Si usas el modo Claude Desktop +
   Pro, Claude Desktop maneja la conexión por su cuenta.

### "¿Por qué no usan un LLM local? Así no pago nada al mes."

Lo evaluamos y se descartó para esta versión por una razón práctica:
**en hardware típico de despacho** (laptop con 8-16 GB RAM, sin GPU
dedicada), los LLMs locales que caben (Gemma 2B, Llama 3 8B, etc.) **no
dan la calidad de razonamiento jurídico** que el protocolo de 5 rondas
necesita. Inventan criterios, confunden circuitos, no siguen la
metodología.

Lo seguimos monitoreando. Si en los próximos meses sale un modelo chico
que sí da la talla, lo añadimos como Modelo 4 sin que cambie nada de la
BD ni de las tools.

---

## Sobre el día a día

### "¿Tengo que aprender a hablarle a Claude?"

No. Le escribes el caso como se lo describirías a un colega:

> "Tengo un cliente que es jubilado del ISSSTE, su esposa quedó sin
> pensión por viudez porque no estaban casados pero llevaban 18 años
> juntos y dos hijos. Quiero promover amparo. ¿Qué jurisprudencia tengo
> a favor?"

Claude (o el CLI) ejecuta el protocolo solo: busca, lee, contradicción,
cruza, te devuelve los criterios obligatorios primero y los persuasivos
después.

### "¿Y si Claude se equivoca?"

Puede pasar. Por eso el formato de respuesta **siempre incluye el
`id_tesis` y el código (`tesis_codigo`) de cada criterio citado**, para
que tú lo verifiques en el SJF antes de pegarlo en un escrito.

Regla de oro: **nunca cites en un escrito una tesis que no hayas
abierto y leído**. La herramienta acelera tu búsqueda; no sustituye tu
juicio profesional.

### "¿Cada cuándo se actualiza la herramienta misma?"

Las versiones del software (no de la BD) se publican según se vayan
arreglando bugs y añadiendo features. Estás recibiendo **v1.2.0**. Los
cambios se documentan en `CHANGELOG.md`. La BD se actualiza
**automáticamente cada semana**.

### "¿Y si tengo un problema o quiero pedir una feature?"

[Aquí va tu canal de soporte: email, WhatsApp, lo que prefieras.]

---

## Sobre la confianza

### "¿Cómo sé que la BD no tiene errores?"

- Hay un script de validación: `python scripts/validar_bd.py`. Verifica
  integridad SQLite, integridad del índice FTS5, drift entre la tabla y
  el índice, y los triggers de sincronización. Sale con código 1 si
  algo está mal.
- Hay 82 tests automatizados (`pytest tests/`) que protegen contra
  regresiones.
- La BD se sincroniza con la API oficial de la SCJN. No es información
  inventada, es un mirror local.

### "¿Y mis casos? ¿Se quedan en algún servidor?"

- En el modo **Claude Desktop + Pro**: tus mensajes los procesa
  Anthropic según su política de privacidad. Por defecto Anthropic no
  entrena con datos de Pro, pero verifícalo en su sitio.
- En el modo **CLI con API**: lo mismo — los casos pasan por la API de
  Anthropic.
- En el modo **Solo BD**: nada sale de tu computadora. Cero red.

Si manejas casos sensibles y la confidencialidad es crítica, el Modelo 3
(SQL directo) es la opción más segura, aunque también la menos cómoda.

### "¿Y si quiero ver el código?"

El producto incluye el código fuente completo de Python en
`scjn_core/`, `server/`, `cli/`, `scripts/`, `tests/`. Puedes
inspeccionarlo, validarlo, e incluso modificarlo (sujeto a la licencia).
Lo único cerrado son los binarios `.exe` precompilados, pero esos solo
son una conveniencia: el código fuente que generó el .exe está al lado.
