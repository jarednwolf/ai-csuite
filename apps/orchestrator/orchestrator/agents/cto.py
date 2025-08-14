def plan_impl(state: dict) -> dict:
    state["log"].append("CTO: wrote plan + ADR")
    state["plan"] = {"tasks": ["implement feature", "write tests"]}
    return state


