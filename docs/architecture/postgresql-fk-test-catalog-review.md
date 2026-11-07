# Revisión de calidad del catálogo de pruebas FK — Issue #25

## Resultado de la revisión

Se contrastaron:
- `postgresql-physical-schema.md` (contrato físico v0.8 y reglas específicas de §13);
- `postgresql-fk-normalized-matrix.md` (60 relaciones);
- `postgresql-fk-candidate-key-audit.md` (12 claves compuestas);
- `tests/postgresql/fk-integrity-test-catalog.md` (120 escenarios).

### Cobertura estructural verificada

| Comprobación | Resultado |
|---|---:|
| Relaciones FK con ID único | 60/60 |
| Tablas cubiertas por inventario | 34/34 |
| Claves compuestas destino inventariadas | 12 |
| Casos positivos catalogados | 60 |
| Casos negativos catalogados | 60 |
| Total de escenarios | 120 |
| IDs de prueba faltantes | 0 |
| IDs FK duplicados | 0 |

Esta validación comprueba estructura documental y presencia de IDs; no ejecuta SQL ni demuestra que el DDL implemente las relaciones.

## Hallazgo corregido: falsas aceptaciones por NULL en FK compuestas

La primera redacción de varios casos negativos decía alterar un componente de la tupla sin exigir que todos los componentes fueran NOT NULL. Bajo PostgreSQL `MATCH SIMPLE`, un NULL en cualquier columna de la FK compuesta puede hacer que la referencia no se compruebe. Por tanto, algunos escenarios negativos podrían haber sido aceptados legítimamente y no demostrar una violación referencial.

Se corrigieron los ocho casos negativos compuestos genéricos:
- FK-003
- FK-004
- FK-006
- FK-011
- FK-012
- FK-039
- FK-045
- FK-048

Ahora conservan todos los componentes NOT NULL y cambian exactamente uno frente a una tupla destino válida. Los casos NULL se reservan para pruebas separadas de semántica MATCH/nulabilidad.

## Distinción de resultados esperados

- FK inexistente o tupla compuesta no coincidente: SQLSTATE `23503`.
- CHECK incumplido: SQLSTATE `23514` (salvo que una implementación explícita use otro mecanismo).
- UNIQUE duplicado: SQLSTATE `23505`.
- Trigger/función: verificar el SQLSTATE y constraint/message contractual que se apruebe; no etiquetar automáticamente como `23503`.

Los casos de identidad, accepted mappings, cadenas append-only, scope y concurrencia necesitan aserciones sobre CHECKs, índices y triggers, además de las FKs. El catálogo lo separa en escenarios específicos y pruebas transversales.

## Bloqueos que permanecen

1. Las 60 relaciones siguen siendo una normalización documental que debe cotejarse con DDL ejecutable.
2. Las 12 claves destino deben existir como PK/UNIQUE no parciales y con orden exacto en el esquema global.
3. MATCH, ON UPDATE/DELETE y diferibilidad deben aprobarse relación por relación; los defaults provisionales no se elevan a contrato por aparecer en la matriz.
4. Las funciones/triggers de cadena, scope, mapping accepted y linaje requieren pruebas reales con dos sesiones concurrentes.
5. Los 120 casos son especificaciones, no código ejecutable ni resultados de PostgreSQL.

## Dictamen

El catálogo alcanza cobertura estructural 60/60 y se corrigió el defecto de diseño más peligroso de sus negativos compuestos: el bypass de MATCH SIMPLE por NULL. El siguiente paso válido no es declarar las pruebas listas, sino materializar el DDL completo y convertir estos escenarios en pruebas SQL ejecutadas contra PostgreSQL 16 desde una base vacía.
