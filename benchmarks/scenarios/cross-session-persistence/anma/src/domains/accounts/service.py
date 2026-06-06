"""accounts public surface. Kept decoupled from billing (see prior decision)."""

def get_user(user_id: str) -> dict:
    return {"id": user_id, "name": "Ada"}

def account_summary(user_id: str, invoiced: int = 0) -> dict:
    # `invoiced` is injected by the caller to keep accounts decoupled from billing
    u = get_user(user_id)
    return {**u, "invoiced": invoiced}
