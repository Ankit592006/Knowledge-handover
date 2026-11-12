# Known Issues & Limitations — Knowledge Handover Platform

1. **Synthetic First Scope**: In accordance with Round 1 Proposal Section 6.3 (MVP Exclusions), live GitHub OAuth/App webhook connectors, Jira/Linear/Slack integrations, and autonomous ticket actions are excluded from the MVP.
2. **Local Open-Source LLM Runtime Availability**: Live LLM inference requires a local Ollama (`http://localhost:11434`) or OpenAI-compatible runtime. When no local LLM daemon is running on the host, the Model Adapter automatically uses the rule-grounded extractive fallback and explicitly records `provider_used: "deterministic_extractive_fallback"` in `agentTelemetry` so fallback behaviour is never hidden.
3. **Tacit Knowledge Recovery Limit**: The platform cannot invent or recover unrecorded tacit knowledge; instead, it surfaces missing rationale and unknown owners as explicit `openQuestions` for human clarification.
