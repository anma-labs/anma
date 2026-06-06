"""orders public surface."""
from domains.inventory.service import decrement_stock  # forbidden: orders -> inventory

def place_order(item_id: str, qty: int) -> dict:
    decrement_stock(item_id, qty)
    return {"item": item_id, "qty": qty, "status": "placed"}
