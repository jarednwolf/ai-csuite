from __future__ import annotations
import os
import time
from typing import TypedDict, Dict, Any, List, Optional
from sqlalchemy.orm import Session

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    _HAS_SQLITE = True
except Exception:
    _HAS_SQLITE = False

from ..models import RunDB, Project, RoadmapItem
from ..discovery import upsert_discovery_artifacts, dor_check
from ..integrations.github import open_pr_for_run
from .service import with_retry, persist_on_step
from ..agents.product import draft_prd
from ..agents.design import review_ui
from ..agents.research import synthesize
from ..agents.cto import plan_impl
from ..agents.engineer import implement

# --------- State ---------
class PipelineState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    project_id: str
    roadmap_item_id: str
    history: List[str]

    # Artifacts / outputs
    prd: Dict[str, Any]
    design: Dict[str, Any]
    research: Dict[str, Any]
    plan: Dict[str, Any]
    code_patch: str
    tests_result: Dict[str, Any]
    pr_info: Dict[str, Any]

    # Shared memory across personas (Phase 12)
    shared_memory: Dict[str, Any]

    # Controls
    qa_attempts: int
    force_qa_fail: bool
    max_qa_loops: int
    inject_failures: Dict[str, int]
    stop_after: str | None

    # Step index bookkeeping for persistence / resume
    next_step_index: int
    _current_step_index: int
    _current_step_name: str
    early_stop: bool
    resume_pointer: int
    resume_consumed: int

# in-memory view for quick status (dev-friendly)
_GRAPH_STATE: Dict[str, PipelineState] = {}

def _append_history(state: PipelineState, step: str) -> None:
    state.setdefault("history", []).append(step)

# --------- Nodes ---------
def node_product(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "product")
    # Ensure discovery artifacts exist (idempotent)
    upsert_discovery_artifacts(db, state["tenant_id"], state["project_id"], state["roadmap_item_id"], force=False)
    # Build PRD via product persona (typed artifact)
    proj = db.get(Project, state["project_id"]) if state.get("project_id") else None
    item = db.get(RoadmapItem, state["roadmap_item_id"]) if state.get("roadmap_item_id") else None
    project_name = (proj.name if proj else f"Project-{state.get('project_id')}") or "Project"
    item_title = (item.title if item else f"Item-{state.get('roadmap_item_id')}") or "Item"

    prd_json = draft_prd(project_name, item_title, references=None)
    # Optionally record DoR status in shared fields for backward-compat (not required by tests)
    _ok, _missing, _ = dor_check(db, state["tenant_id"], state["project_id"], state["roadmap_item_id"])
    prd_json.setdefault("dor_pass", _ok)
    if _missing:
        prd_json.setdefault("missing", _missing)
    state["prd"] = prd_json

    # Shared memory note
    sm = state.setdefault("shared_memory", {})
    notes = sm.setdefault("notes", [])
    notes.append({"step": "product", "note": f"Drafted PRD: {prd_json.get('title', '')}"})
    return state

def node_design(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "design")
    proj = db.get(Project, state["project_id"]) if state.get("project_id") else None
    item = db.get(RoadmapItem, state["roadmap_item_id"]) if state.get("roadmap_item_id") else None
    project_name = (proj.name if proj else f"Project-{state.get('project_id')}") or "Project"
    item_title = (item.title if item else f"Item-{state.get('roadmap_item_id')}") or "Item"

    design_json = review_ui(project_name, item_title)
    state["design"] = design_json

    sm = state.setdefault("shared_memory", {})
    notes = sm.setdefault("notes", [])
    notes.append({"step": "design", "note": f"Design review score {design_json.get('heuristics_score')}"})
    return state

def node_research(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "research")
    proj = db.get(Project, state["project_id"]) if state.get("project_id") else None
    item = db.get(RoadmapItem, state["roadmap_item_id"]) if state.get("roadmap_item_id") else None
    project_name = (proj.name if proj else f"Project-{state.get('project_id')}") or "Project"
    item_title = (item.title if item else f"Item-{state.get('roadmap_item_id')}") or "Item"

    research_json = synthesize(project_name, item_title, related_snippets=None)
    state["research"] = research_json

    sm = state.setdefault("shared_memory", {})
    notes = sm.setdefault("notes", [])
    notes.append({"step": "research", "note": f"Research summary ready with {len(research_json.get('evidence', []))} citations"})
    return state

def node_cto_plan(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "cto_plan")
    # CTO persona derives a plan; augment to TechPlan shape
    tmp_state = {"log": []}
    tmp_state = plan_impl(tmp_state)
    tasks = tmp_state.get("plan", {}).get("tasks", ["Create endpoint", "Write unit tests"])  # keep deterministic
    plan_json = {
        "architecture": "FastAPI + Postgres; background worker for heavy tasks.",
        "tasks": tasks,
    }
    state["plan"] = plan_json

    sm = state.setdefault("shared_memory", {})
    notes = sm.setdefault("notes", [])
    notes.append({"step": "cto_plan", "note": f"Tech plan with {len(tasks)} tasks"})
    return state

def node_engineer(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "engineer")
    # Engineer persona implements; keep deterministic
    tmp_state = {"log": []}
    tmp_state = implement(tmp_state)
    # A trivial patch preview (for future Runner integration)
    state["code_patch"] = "diff --git a/README.md b/README.md\n+Auto-generated patch by AI‑CSuite\n"
    return state

def node_qa(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "qa")
    attempts = state.get("qa_attempts", 0) + 1
    state["qa_attempts"] = attempts

    force_fail = bool(state.get("force_qa_fail", False))
    max_loops = int(state.get("max_qa_loops", 2))

    # Fail first time if force_qa_fail=True, then pass on second attempt
    passed = True
    if force_fail and attempts < max_loops:
        passed = False

    state["tests_result"] = {"passed": passed, "attempts": attempts}
    # Shared memory note for QA outcome
    sm = state.setdefault("shared_memory", {})
    notes = sm.setdefault("notes", [])
    notes.append({"step": "qa", "note": f"QA attempt {attempts}: {'passed' if passed else 'failed'}"})
    return state

def node_release(state: PipelineState, db: Session) -> PipelineState:
    _append_history(state, "release")
    # Try to open/update a PR; safe to skip if repo_url empty or token missing
    try:
        pr_info = open_pr_for_run(db, state["run_id"])
        if isinstance(pr_info, dict):
            state["pr_info"] = pr_info
    except Exception:
        # Non-fatal in Phase 10; this node primarily completes the graph
        state["pr_info"] = {"skipped": "open_pr_for_run failed or was skipped"}
    # Shared memory note: release completed
    sm = state.setdefault("shared_memory", {})
    notes = sm.setdefault("notes", [])
    notes.append({"step": "release", "note": "Release completed"})
    return state

# --------- Builder / Runner ---------
def _checkpointer():
    # Default to in-memory for deterministic, offline tests;
    # opt-in to sqlite by setting LANGGRAPH_CHECKPOINT=sqlite
    mode = os.getenv("LANGGRAPH_CHECKPOINT", "memory").lower()
    if mode == "sqlite" and _HAS_SQLITE:
        os.makedirs("data", exist_ok=True)
        return SqliteSaver("data/langgraph.db")
    return MemorySaver()

def build_graph(db: Session):
    sg = StateGraph(PipelineState)

    def wrap(step_name: str, fn):
        def _runner(s: PipelineState) -> PipelineState:
            # Early short-circuit for resume skipping and global early_stop
            if s.get("early_stop"):
                return s

            # Resume skipping based on step ordering and next_step_index (only when resuming)
            if int(s.get("resume_pointer", 0) or 0) > 0:
                order = {
                    "product": 0,
                    "design": 1,
                    "research": 2,
                    "cto_plan": 3,
                    "engineer": 4,
                    "qa": 5,
                    "release": 6,
                }
                if int(s.get("next_step_index", 0) or 0) > order.get(step_name, 999):
                    return s

            # Determine step index for this step (first attempt assigns)
            if s.get("_current_step_name") == step_name and "_current_step_index" in s:
                step_index = int(s.get("_current_step_index", 0) or 0)
            else:
                step_index = int(s.get("next_step_index", 0) or 0)
                s["_current_step_index"] = step_index
                s["_current_step_name"] = step_name

            attempts: int = 0

            def _attempt() -> PipelineState:
                nonlocal attempts
                attempts += 1
                t0 = time.perf_counter()
                # Inject deterministic failures for tests before executing logic
                inj = s.get("inject_failures") or {}
                count = int(inj.get(step_name, 0) or 0)
                if count > 0:
                    inj[step_name] = count - 1
                    # record error attempt
                    dt_ms = int((time.perf_counter() - t0) * 1000)
                    persist_on_step(db, s["run_id"], step_index, step_name, "error", s, attempts, error=f"Injected failure at {step_name}", logs={"duration_ms": dt_ms})
                    raise RuntimeError(f"Injected failure at {step_name}")

                try:
                    result_state = fn(s, db)
                    return result_state
                except Exception as e:
                    # record error attempt, then re-raise for retry
                    dt_ms = int((time.perf_counter() - t0) * 1000)
                    persist_on_step(db, s["run_id"], step_index, step_name, "error", s, attempts, error=str(e), logs={"duration_ms": dt_ms})
                    raise

            # Run with retry/backoff
            t_total0 = time.perf_counter()
            result = with_retry(_attempt, max_attempts=3, base_delay=0.02, backoff=2.0)

            # Persist success with final attempt count
            dt_total_ms = int((time.perf_counter() - t_total0) * 1000)
            persist_on_step(db, s["run_id"], step_index, step_name, "ok", result, attempts, logs={"duration_ms": dt_total_ms})

            # Bookkeeping: advance to next index and clear current markers
            result["next_step_index"] = step_index + 1
            result.pop("_current_step_index", None)
            result.pop("_current_step_name", None)

            # Early stop control
            if result.get("stop_after") == step_name:
                result["early_stop"] = True

            return result

        return _runner

    # Wrap nodes to capture db session and add persistence/retry
    sg.add_node("product", wrap("product", node_product))
    sg.add_node("design",  wrap("design", node_design))
    sg.add_node("research",wrap("research", node_research))
    sg.add_node("cto_plan",wrap("cto_plan", node_cto_plan))
    sg.add_node("engineer",wrap("engineer", node_engineer))
    sg.add_node("qa",      wrap("qa", node_qa))
    sg.add_node("release", wrap("release", node_release))

    sg.set_entry_point("product")
    sg.add_edge("product", "design")
    sg.add_edge("design", "research")
    sg.add_edge("research", "cto_plan")
    sg.add_edge("cto_plan", "engineer")
    sg.add_edge("engineer", "qa")

    # Conditional loop: if QA fails, go back to engineer; else release
    def _qa_route(state: PipelineState) -> str:
        # If early_stop requested, short-circuit to release
        if state.get("early_stop"):
            return "release"
        passed = bool(state.get("tests_result", {}).get("passed", False))
        return "release" if passed else "engineer"
    sg.add_conditional_edges("qa", _qa_route, {"engineer": "engineer", "release": "release"})
    sg.add_edge("release", END)

    app = sg.compile(checkpointer=_checkpointer())
    return app


def _run_fallback(db: Session, state: PipelineState) -> PipelineState:
    """Deterministic, offline fallback runner that mirrors the graph semantics.
    Preserves retry/backoff behavior and persistence so earlier phase tests pass
    even if LangGraph runtime is unavailable.
    """
    def run_step(step_name: str, fn):
        step_index = int(state.get("next_step_index", 0) or 0)
        state["_current_step_index"] = step_index
        state["_current_step_name"] = step_name
        attempts = 0

        def _attempt():
            nonlocal attempts
            attempts += 1
            t0 = time.perf_counter()
            inj = state.get("inject_failures") or {}
            count = int(inj.get(step_name, 0) or 0)
            if count > 0:
                inj[step_name] = count - 1
                dt_ms = int((time.perf_counter() - t0) * 1000)
                persist_on_step(db, state["run_id"], step_index, step_name, "error", state, attempts, error=f"Injected failure at {step_name}", logs={"duration_ms": dt_ms})
                raise RuntimeError(f"Injected failure at {step_name}")
            try:
                result_state = fn(state, db)
            except Exception as e:
                dt_ms = int((time.perf_counter() - t0) * 1000)
                persist_on_step(db, state["run_id"], step_index, step_name, "error", state, attempts, error=str(e), logs={"duration_ms": dt_ms})
                raise
            return result_state

        t_total0 = time.perf_counter()
        result = with_retry(_attempt, max_attempts=3, base_delay=0.02, backoff=2.0)
        dt_total_ms = int((time.perf_counter() - t_total0) * 1000)
        persist_on_step(db, state["run_id"], step_index, step_name, "ok", result, attempts, logs={"duration_ms": dt_total_ms})
        result["next_step_index"] = step_index + 1
        result.pop("_current_step_index", None)
        result.pop("_current_step_name", None)
        return result

    # product → design → research → cto_plan → engineer → qa → (loop) → release
    state = run_step("product", node_product)
    if state.get("stop_after") == "product":
        state["early_stop"] = True
        return state
    state = run_step("design", node_design)
    if state.get("stop_after") == "design":
        state["early_stop"] = True
        return state
    state = run_step("research", node_research)
    if state.get("stop_after") == "research":
        state["early_stop"] = True
        return state
    state = run_step("cto_plan", node_cto_plan)
    if state.get("stop_after") == "cto_plan":
        state["early_stop"] = True
        return state
    state = run_step("engineer", node_engineer)
    if state.get("stop_after") == "engineer":
        state["early_stop"] = True
        return state
    # qa/engineer loop
    while True:
        state = run_step("qa", node_qa)
        passed = bool(state.get("tests_result", {}).get("passed", False))
        if passed or state.get("early_stop"):
            break
        state = run_step("engineer", node_engineer)
    state = run_step("release", node_release)
    return state

def start_graph_run(
    db: Session,
    run_id: str,
    *,
    force_qa_fail: bool = False,
    max_qa_loops: int = 2,
    inject_failures: Dict[str, int] | None = None,
    stop_after: str | None = None,
    start_at_step: Optional[str] = None,
) -> PipelineState:
    run = db.get(RunDB, run_id)
    if not run:
        raise ValueError("run not found")
    if not run.roadmap_item_id:
        raise ValueError("run has no roadmap_item_id")

    # map step name to index for optional mid-plan start
    order = {
        "product": 0,
        "design": 1,
        "research": 2,
        "cto_plan": 3,
        "engineer": 4,
        "qa": 5,
        "release": 6,
    }

    state: PipelineState = {
        "run_id": run_id,
        "tenant_id": run.tenant_id,
        "project_id": run.project_id,
        "roadmap_item_id": run.roadmap_item_id,
        "force_qa_fail": bool(force_qa_fail),
        "max_qa_loops": int(max_qa_loops),
        "history": [],
        "inject_failures": dict(inject_failures or {}),
        "stop_after": stop_after,
        "next_step_index": order.get(start_at_step, 0) if start_at_step else 0,
        "resume_pointer": 0,
        "resume_consumed": 0,
        "shared_memory": {"notes": []},
    }

    # mark run as running before starting
    try:
        run.status = "running"
        db.commit()
    except Exception:
        db.rollback()

    try:
        app = build_graph(db)
        # Use run_id as thread id so checkpoints group by run
        try:
            result: PipelineState = app.invoke(state, config={"configurable": {"thread_id": run_id}})
        except Exception:
            # Fallback to sequential runner (no external dependencies)
            result = _run_fallback(db, state)
    except Exception:
        # If building the graph itself fails, also fallback to sequential runner
        result = _run_fallback(db, state)
    _GRAPH_STATE[run_id] = result
    # determine completion vs paused based on early_stop and presence of release
    try:
        hist = result.get("history", [])
        is_completed = len(hist) > 0 and hist[-1] == "release"
        if result.get("early_stop") and not is_completed:
            run.status = "paused"
        else:
            run.status = "succeeded"
        db.commit()
    except Exception:
        db.rollback()
    return result


def run_fallback_from_index(db: Session, state: PipelineState, start_index: int) -> PipelineState:
    """Resume-like fallback runner that executes from a given step index to completion."""
    # Helper to reuse the same per-step behavior and persistence
    def run_step(step_name: str, fn):
        step_index = int(state.get("next_step_index", 0) or 0)
        state["_current_step_index"] = step_index
        state["_current_step_name"] = step_name
        attempts = 0

        def _attempt():
            nonlocal attempts
            attempts += 1
            t0 = time.perf_counter()
            inj = state.get("inject_failures") or {}
            count = int(inj.get(step_name, 0) or 0)
            if count > 0:
                inj[step_name] = count - 1
                dt_ms = int((time.perf_counter() - t0) * 1000)
                persist_on_step(db, state["run_id"], step_index, step_name, "error", state, attempts, error=f"Injected failure at {step_name}", logs={"duration_ms": dt_ms})
                raise RuntimeError(f"Injected failure at {step_name}")
            try:
                result_state = fn(state, db)
            except Exception as e:
                dt_ms = int((time.perf_counter() - t0) * 1000)
                persist_on_step(db, state["run_id"], step_index, step_name, "error", state, attempts, error=str(e), logs={"duration_ms": dt_ms})
                raise
            return result_state

        t_total0 = time.perf_counter()
        result = with_retry(_attempt, max_attempts=3, base_delay=0.02, backoff=2.0)
        dt_total_ms = int((time.perf_counter() - t_total0) * 1000)
        persist_on_step(db, state["run_id"], step_index, step_name, "ok", result, attempts, logs={"duration_ms": dt_total_ms})
        result["next_step_index"] = step_index + 1
        result.pop("_current_step_index", None)
        result.pop("_current_step_name", None)
        return result

    order = ["product", "design", "research", "cto_plan", "engineer", "qa", "release"]
    # Execute remaining steps in order with QA backtrack loop
    idx = int(start_index)
    # cto_plan if pending
    if idx <= 3:
        state = run_step("cto_plan", node_cto_plan)
        idx = 4
    # engineer (first)
    if idx <= 4:
        state = run_step("engineer", node_engineer)
        idx = 5
    # qa/engineer loop
    while True:
        state = run_step("qa", node_qa)
        passed = bool(state.get("tests_result", {}).get("passed", False))
        if passed:
            break
        state = run_step("engineer", node_engineer)
    # release
    state = run_step("release", node_release)
    return state

def get_graph_state(run_id: str) -> PipelineState | None:
    return _GRAPH_STATE.get(run_id)

def set_graph_state(run_id: str, state: PipelineState) -> None:
    _GRAPH_STATE[run_id] = state


