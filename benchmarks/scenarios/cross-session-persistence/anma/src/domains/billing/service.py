"""billing public surface. May import accounts."""
from domains.accounts.service import get_user

def total_invoiced(user_id: str) -> int:
    return 0
