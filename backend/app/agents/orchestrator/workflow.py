"""LangGraph Multi-Agent Workflow Orchestrator (Module 8)."""

from datetime import datetime, timezone
from typing import Any, Dict, Literal

from app.agents.evidence_verification.agent import run_evidence_verification_agent
from app.agents.knowledge_extraction.agent import run_knowledge_extraction_agent
from app.agents.risk_dependency.agent import run_risk_dependency_agent
from app.agents.schemas import HandoverGraphState
from app.core.config import get_settings

settings = get_settings()

try:
    from langgraph.graph import END, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


def node_knowledge_extraction(state: HandoverGraphState) -> HandoverGraphState:
    telemetry = dict(state.get("agent_telemetry", {}))
    errors = list(state.get("errors", []))
    max_retries = settings.LLM_MAX_RETRIES

    if state.get("force_failure_agent") == "knowledge_extraction":
        errors.append("Agent 1 (Knowledge Extraction) failed after bounded retries: forced failure test.")
        telemetry["agent_1_knowledge_extraction"] = {"status": "failed", "attempts": max_retries}
        return {**state, "agent_telemetry": telemetry, "errors": errors, "halted": True}

    passages = state.get("retrieved_passages", [])
    for attempt in range(1, max_retries + 1):
        try:
            out, meta = run_knowledge_extraction_agent(passages)
            telemetry["agent_1_knowledge_extraction"] = {
                "status": "completed",
                "attempts": attempt,
                "claims_extracted": len(out.candidate_claims),
                "questions_extracted": len(out.unresolved_questions),
                **meta.model_dump(),
            }
            return {
                **state,
                "project_summary": out.project_summary,
                "candidate_claims": [c.model_dump() for c in out.candidate_claims],
                "unresolved_questions": out.unresolved_questions,
                "agent_telemetry": telemetry,
                "halted": False,
            }
        except Exception as exc:
            if attempt >= max_retries:
                errors.append(f"Agent 1 (Knowledge Extraction) failed: {exc}")
                telemetry["agent_1_knowledge_extraction"] = {"status": "failed", "attempts": attempt, "error": str(exc)}
                return {**state, "agent_telemetry": telemetry, "errors": errors, "halted": True}
    return state


def node_risk_dependency(state: HandoverGraphState) -> HandoverGraphState:
    if state.get("halted"):
        return state

    telemetry = dict(state.get("agent_telemetry", {}))
    errors = list(state.get("errors", []))
    max_retries = settings.LLM_MAX_RETRIES

    if state.get("force_failure_agent") == "risk_dependency":
        errors.append("Agent 3 (Risk & Dependency) failed after bounded retries: forced failure test.")
        telemetry["agent_3_risk_dependency"] = {"status": "failed", "attempts": max_retries}
        return {**state, "agent_telemetry": telemetry, "errors": errors, "halted": True}

    claims = state.get("candidate_claims", [])
    passages = state.get("retrieved_passages", [])
    for attempt in range(1, max_retries + 1):
        try:
            out, meta = run_risk_dependency_agent(claims, passages)
            telemetry["agent_3_risk_dependency"] = {
                "status": "completed",
                "attempts": attempt,
                "risks_and_dependencies_count": len(out.risks_and_dependencies),
                "next_actions_count": len(out.next_actions),
                **meta.model_dump(),
            }
            return {
                **state,
                "risks_and_dependencies": [r.model_dump() for r in out.risks_and_dependencies],
                "next_actions": [a.model_dump() for a in out.next_actions],
                "agent_telemetry": telemetry,
                "halted": False,
            }
        except Exception as exc:
            if attempt >= max_retries:
                errors.append(f"Agent 3 (Risk & Dependency) failed: {exc}")
                telemetry["agent_3_risk_dependency"] = {"status": "failed", "attempts": attempt, "error": str(exc)}
                return {**state, "agent_telemetry": telemetry, "errors": errors, "halted": True}
    return state


def node_evidence_verification(state: HandoverGraphState) -> HandoverGraphState:
    if state.get("halted"):
        return state

    telemetry = dict(state.get("agent_telemetry", {}))
    errors = list(state.get("errors", []))
    max_retries = settings.LLM_MAX_RETRIES

    if state.get("force_failure_agent") == "evidence_verification":
        errors.append("Agent 2 (Evidence Verification) failed after bounded retries: forced failure test.")
        telemetry["agent_2_evidence_verification"] = {"status": "failed", "attempts": max_retries}
        return {**state, "agent_telemetry": telemetry, "errors": errors, "halted": True}

    claims = state.get("candidate_claims", [])
    passages = state.get("retrieved_passages", [])
    for attempt in range(1, max_retries + 1):
        try:
            out, meta = run_evidence_verification_agent(claims, passages)
            ver_map = {v.claim_code: v.model_dump() for v in out.verifications}
            telemetry["agent_2_evidence_verification"] = {
                "status": "completed",
                "attempts": attempt,
                "claims_verified": len(ver_map),
                **meta.model_dump(),
            }
            return {
                **state,
                "verification_map": ver_map,
                "agent_telemetry": telemetry,
                "halted": False,
            }
        except Exception as exc:
            if attempt >= max_retries:
                errors.append(f"Agent 2 (Evidence Verification) failed: {exc}")
                telemetry["agent_2_evidence_verification"] = {"status": "failed", "attempts": attempt, "error": str(exc)}
                return {**state, "agent_telemetry": telemetry, "errors": errors, "halted": True}
    return state


def _route_after_node(state: HandoverGraphState) -> Literal["continue", "halt"]:
    if state.get("halted") or state.get("errors"):
        return "halt"
    return "continue"


def execute_handover_orchestration(initial_state: HandoverGraphState) -> HandoverGraphState:
    """Compile and execute the 3-agent LangGraph state machine with conditional stop-on-failure routing."""
    state: HandoverGraphState = {
        "errors": [],
        "halted": False,
        "agent_telemetry": {
            "orchestrator": "langgraph" if LANGGRAPH_AVAILABLE else "state_graph_runner",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        **initial_state,
    }

    if LANGGRAPH_AVAILABLE:
        workflow = StateGraph(HandoverGraphState)
        workflow.add_node("knowledge_extraction", node_knowledge_extraction)
        workflow.add_node("risk_dependency", node_risk_dependency)
        workflow.add_node("evidence_verification", node_evidence_verification)

        workflow.set_entry_point("knowledge_extraction")
        workflow.add_conditional_edges(
            "knowledge_extraction",
            _route_after_node,
            {"continue": "risk_dependency", "halt": END},
        )
        workflow.add_conditional_edges(
            "risk_dependency",
            _route_after_node,
            {"continue": "evidence_verification", "halt": END},
        )
        workflow.add_edge("evidence_verification", END)

        compiled = workflow.compile()
        final_state: HandoverGraphState = compiled.invoke(state)
    else:
        s1 = node_knowledge_extraction(state)
        if _route_after_node(s1) == "halt":
            final_state = s1
        else:
            s2 = node_risk_dependency(s1)
            if _route_after_node(s2) == "halt":
                final_state = s2
            else:
                final_state = node_evidence_verification(s2)

    telemetry = dict(final_state.get("agent_telemetry", {}))
    telemetry["completed_at"] = datetime.now(timezone.utc).isoformat()
    telemetry["publication_blocked"] = bool(final_state.get("halted"))
    final_state["agent_telemetry"] = telemetry
    return final_state
