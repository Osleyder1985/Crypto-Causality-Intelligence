# Architecture Decision Records

## Status

Initial decisions for the Historical Market Intelligence data foundation. These decisions establish a starting point and may be revised through documented evidence and review.

## ADR-001: Strict point-in-time availability

**Status:** Accepted

**Decision:** Research and backtesting datasets use only information demonstrably available by the analysis cutoff. Event time, publication time, capture time, ingestion time, and availability time remain distinct.

**Rationale:** Prevent look-ahead bias and make historical simulations representative of information that could actually have been known.

**Consequences:** Some records with unknown availability cannot be used in strict point-in-time analysis. Late-arriving data and revisions require explicit handling.

**Alternatives considered:**
- Treat event time as availability time: rejected because it backdates later information.
- Use publication time universally: insufficient when publication timestamps are absent, unreliable, or not independently verifiable.
- Use capture time universally: conservative and defensible, but may not represent public availability before platform capture. The selected policy records both and applies a declared rule.

## ADR-002: Layered data organization

**Status:** Accepted

**Decision:** Separate raw, normalized, research/evidence, and derived data responsibilities.

**Rationale:** Preserve original evidence, isolate provider-specific formats, and make transformations auditable.

**Consequences:** Requires lineage metadata and additional storage. The layers are logical boundaries and do not require separate services or databases.

**Alternatives considered:**
- One mutable unified dataset: rejected because it obscures source fidelity and transformation history.
- Separate distributed services for every layer: deferred as premature operational complexity.

## ADR-003: Broad conceptual model, incremental implementation

**Status:** Accepted

**Decision:** Define identity, market observations, sources, documents, events, evidence, claims, hypotheses, and lineage in the conceptual model. Implement them incrementally according to validated priorities.

**Rationale:** The research domain requires relationships between market behavior and information while preserving the distinction between observations and interpretations.

**Consequences:** The initial schema may be broader than the first working ingestion pipeline. Physical schema and implementation sequencing remain open to refinement.

## ADR-004: Provider-neutral canonical model

**Status:** Accepted

**Decision:** Use internal identifiers and canonical definitions while retaining source-native identifiers and values. Isolate provider-specific behavior behind adapters.

**Rationale:** Avoid binding the research model to one exchange, vendor, or API.

**Consequences:** Entity resolution and identifier mapping require explicit governance, especially for ambiguous symbols, wrapped assets, and token migrations.

## ADR-005: No premature infrastructure selection

**Status:** Accepted

**Decision:** Defer final database, object storage, streaming, and deployment choices until workload, volume, latency, budget, retention, and query requirements are documented.

**Rationale:** Select the simplest architecture that meets measured requirements rather than introducing infrastructure without evidence.

**Consequences:** This document defines logical responsibilities, not a final technology stack.

## Open questions

1. Which initial market coverage and candle intervals are required for the first research dataset?
2. Which source categories can be legally and reliably retained, and at what historical depth?
3. What are the expected ingestion frequency, data volume, and query patterns?
4. What retention and reproducibility guarantees are required for raw source material?
5. Which asset identity and market naming standards should be adopted or mapped?
6. What policy should govern records whose publication time is known but whose actual public availability cannot be independently verified?

These questions should be answered before selecting production providers and infrastructure.
