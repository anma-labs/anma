"""accounts public surface. Kept decoupled from billing (see prior decision)."""

def get_user(user_id: str) -> dict:
    return {"id": user_id, "name": "Ada"}

def account_summary(user_id: str, invoiced: int = 0) -> dict:
    u = get_user(user_id)
    return {**u, "invoiced": invoiced}

def monthly_report(user_id: str, invoiced: int = 0) -> dict:
    # stays decoupled: invoiced injected by the caller, per the recorded decision
    u = get_user(user_id)
    return {**u, "invoiced": invoiced}
