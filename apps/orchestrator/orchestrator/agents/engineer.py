def implement(state: dict) -> dict:
    state["log"].append("Engineer: implemented + tests passed")
    state["tests"] = {"unit": "pass", "e2e": "pass"}
    return state


