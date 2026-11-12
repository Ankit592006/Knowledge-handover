# Architecture Decision Records (DECISIONS.md)

## ADR-01: Modular Monolith over Microservices
- **Decision**: Build a single FastAPI modular monolith (`backend/app/`) with explicit boundaries between deterministic services (`app/modules/`) and multi-agent AI (`app/agents/`).
- **Reason**: Eliminates distributed network overhead and simplifies judge deployment within a 24–48h hackathon window while preserving clean domain separation.

## ADR-02: Hybrid Multi-Agent Architecture with Deterministic Validation Gate
- **Decision**: Place a deterministic database validation layer (`app/modules/validation/service.py`) after the LangGraph 3-Agent pipeline.
- **Reason**: LLMs can hallucinate source identifiers or miss permission boundaries; deterministic SQL verification guarantees that no invented `sourceId` or `RESTRICTED` source ever enters the approved handover package.

## ADR-03: Cross-Dialect `EmbeddingVectorType` (`pgvector` + JSON Cosine Fallback)
- **Decision**: Use `pgvector.sqlalchemy.Vector(384)` when connected to PostgreSQL and a JSON vector array with cosine similarity when running on local SQLite.
- **Reason**: Enables zero-friction `pytest` execution on any developer laptop while running native `pgvector` in Docker Compose.
