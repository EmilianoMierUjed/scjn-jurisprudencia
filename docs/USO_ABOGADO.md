# Como usar la herramienta de jurisprudencia SCJN

## Que es esto

Es una herramienta que le da a Claude acceso directo a una base de datos con
mas de 311,000 criterios de la SCJN (jurisprudencias y tesis aisladas, desde
1911 hasta 2026). Claude busca, analiza, clasifica y presenta los criterios
mas relevantes para tu caso.

## Como usarla

1. Abre Claude Desktop
2. Inicia una conversacion nueva
3. Describe tu caso o tu pregunta juridica

### Ejemplos de lo que puedes preguntar

**Busqueda por tema:**
- "Busca jurisprudencia sobre el derecho a la salud en el ISSSTE"
- "Necesito tesis sobre prescripcion adquisitiva en materia civil"
- "Que criterios hay sobre despido injustificado y carga de la prueba?"

**Busqueda para un caso especifico:**
- "Tengo un amparo donde el ISSSTE no cumplio la sentencia. El juez declaro
  infundado el incidente de defecto de cumplimiento. Necesito jurisprudencia
  para el recurso de revision."
- Puedes copiar y pegar parte de tu expediente directamente en la conversacion.

**Consultas directas:**
- "Lee completa la tesis con codigo 1a./J. 45/2023"
- "Busca contradicciones de tesis sobre pension alimenticia"
- "¿Que tan actualizada esta la base de datos?"

## Como leer los resultados

Claude organiza los resultados en 4 categorias:

1. **Criterios Principales** — Los que directamente aplican a tu caso.
   Fijate en el NIVEL (S, A, B, C, D, E):
   - S y A = Jurisprudencia de la SCJN, OBLIGATORIA para todos los tribunales
   - B y C = Jurisprudencia de Circuito, obligatoria en su circuito
   - D y E = Tesis aisladas, orientadoras pero no obligatorias

2. **Criterios de Refuerzo** — Complementan tu argumento.

3. **Criterios de Riesgo** — Lo que tu contraparte PODRIA citar.
   Claude te dice como distinguirlos o neutralizarlos.

4. **Criterios Analogos** — No son identicos pero aplican por extension.

Al final, Claude da un **Resumen Ejecutivo** con la evaluacion de cobertura
(Solida, Moderada, o Debil) y sugiere la linea argumentativa.

## Actualizacion de la base de datos

La base de datos se actualiza automaticamente cada lunes a las 6:00 AM
(la computadora debe estar encendida). Si necesitas actualizar manualmente,
ejecuta el archivo `scripts\actualizar_scjn.bat`.

## Consejos

- **Se especifico.** En vez de "busca sobre amparo", di "busca jurisprudencia
  sobre cumplimiento de sentencia de amparo cuando la autoridad alega
  alta voluntaria del paciente".

- **Pega tu expediente.** Entre mas contexto le des a Claude, mejores
  seran las busquedas. Puedes pegar fragmentos de tu demanda, sentencia,
  o informes de la contraparte.

- **Pide contraargumentos.** Siempre pregunta "que podria citar el contrario"
  para estar preparado.

- **Verifica las tesis.** Claude cita con el codigo de registro para que
  puedas verificar en el Semanario Judicial de la Federacion en linea.
