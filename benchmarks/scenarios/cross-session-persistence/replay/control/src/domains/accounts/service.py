"""accounts public surface."""
from domains.billing.service import total_invoiced  # regression: re-broke the boundary

def get_user(user_id: str) -> dict:
    return {"id": user_id, "name": "Ada"}

def account_summary(user_id: str, invoiced: int = 0) -> dict:
    u = get_user(user_id)
    return {**u, "invoiced": invoiced}

def monthly_report(user_id: str) -> dict:
    u = get_user(user_id)
    return {**u, "invoiced": total_invoiced(user_id)}
