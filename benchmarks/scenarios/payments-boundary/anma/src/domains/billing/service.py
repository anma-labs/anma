"""billing public surface. May import accounts."""
from domains.accounts.service import get_user

def create_invoice(user_id: str, amount: int) -> dict:
    user = get_user(user_id)
    return {"user": user["id"], "amount": amount}

def total_invoiced(user_id: str) -> int:
    return 0
