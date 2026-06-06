"""orders public surface."""
from typing import Callable

def place_order(item_id: str, qty: int,
                on_placed: Callable[[str, int], None] | None = None) -> dict:
    # stock changes delegated to the caller to keep orders decoupled from inventory
    if on_placed is not None:
        on_placed(item_id, qty)
    return {"item": item_id, "qty": qty, "status": "placed"}
