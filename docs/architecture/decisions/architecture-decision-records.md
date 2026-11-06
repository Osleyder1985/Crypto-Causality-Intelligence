# Registros de decisiones de arquitectura

## Estado

Decisiones iniciales para la base de datos de **Historical Market Intelligence**. Estas decisiones establecen un punto de partida y pueden revisarse mediante evidencias y revisión documentadas.

## ADR-001: Disponibilidad estricta point-in-time

**Estado:** Aceptada

**Decisión:** Los datasets de investigación y backtesting utilizan únicamente información cuya disponibilidad antes del corte de análisis pueda demostrarse. La hora del evento, publicación, captura, ingesta y disponibilidad se mantienen diferenciadas.

**Justificación:** Evitar el look-ahead bias y hacer que las simulaciones históricas representen la información que realmente podría haberse conocido.

**Consecuencias:** Algunos registros con disponibilidad desconocida no podrán utilizarse en análisis point-in-time estrictos. Los datos recibidos con retraso y las revisiones requieren un tratamiento explícito.

**Alternativas consideradas:**
- Tratar la hora del evento como hora de disponibilidad: rechazada porque retrotrae información publicada posteriormente.
- Utilizar siempre la hora de publicación: insuficiente cuando las marcas de publicación no existen, no son confiables o no pueden verificarse de forma independiente.
- Utilizar siempre la hora de captura: es conservadora y defendible, pero puede no representar la disponibilidad pública anterior a la captura por la plataforma. La política seleccionada registra ambas y aplica una regla declarada.

## ADR-002: Organización de datos por capas

**Estado:** Aceptada

**Decisión:** Separar las responsabilidades de los datos raw, normalized, de investigación/evidencias y derived.

**Justificación:** Preservar la evidencia original, aislar los formatos específicos de cada proveedor y hacer auditables las transformaciones.

**Consecuencias:** Se requieren metadatos de linaje y almacenamiento adicional. Las capas son límites lógicos y no exigen servicios o bases de datos separados.

**Alternativas consideradas:**
- Un único dataset unificado y mutable: rechazado porque oculta la fidelidad de las fuentes y el historial de transformaciones.
- Servicios distribuidos separados para cada capa: pospuesto por introducir una complejidad operativa prematura.

## ADR-003: Modelo conceptual amplio e implementación incremental

**Estado:** Aceptada

**Decisión:** Definir identidad, observaciones de mercado, fuentes, documentos, eventos, evidencias, afirmaciones, hipótesis y linaje en el modelo conceptual. Implementarlos progresivamente según prioridades validadas.

**Justificación:** El dominio de investigación requiere relacionar el comportamiento del mercado con la información, preservando la distinción entre observaciones e interpretaciones.

**Consecuencias:** El esquema inicial puede ser más amplio que el primer pipeline funcional de ingesta. El esquema físico y la secuencia de implementación quedan abiertos a refinamiento.

## ADR-004: Modelo canónico independiente del proveedor

**Estado:** Aceptada

**Decisión:** Utilizar identificadores internos y definiciones canónicas, conservando los identificadores y valores nativos de las fuentes. Aislar el comportamiento específico de cada proveedor detrás de adapters.

**Justificación:** Evitar que el modelo de investigación dependa de un único exchange, proveedor o API.

**Consecuencias:** La resolución de entidades y el mapeo de identificadores requieren gobernanza explícita, especialmente para símbolos ambiguos, activos wrapped y migraciones de tokens.

## ADR-005: Evitar la selección prematura de infraestructura

**Estado:** Aceptada

**Decisión:** Posponer las decisiones definitivas sobre base de datos, object storage, streaming y despliegue hasta documentar los requisitos de carga, volumen, latencia, presupuesto, retención y consulta.

**Justificación:** Seleccionar la arquitectura más sencilla que satisfaga los requisitos medidos, en lugar de introducir infraestructura sin evidencias.

**Consecuencias:** Este documento define responsabilidades lógicas, no un stack tecnológico definitivo.

## Cuestiones pendientes

1. ¿Qué cobertura inicial de mercados e intervalos de velas se necesita para el primer dataset de investigación?
2. ¿Qué categorías de fuentes pueden conservarse legal y confiablemente, y con qué profundidad histórica?
3. ¿Cuáles son la frecuencia de ingesta, el volumen de datos y los patrones de consulta esperados?
4. ¿Qué garantías de retención y reproducibilidad se requieren para el material raw de las fuentes?
5. ¿Qué estándares de identidad de activos y nomenclatura de mercados deben adoptarse o mapearse?
6. ¿Qué política debe regir los registros cuya hora de publicación se conoce, pero cuya disponibilidad pública efectiva no puede verificarse de forma independiente?

Estas cuestiones deben resolverse antes de seleccionar proveedores e infraestructura de producción.
