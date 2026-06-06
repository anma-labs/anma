"""orders public surface."""

def place_order(item_id: str, qty: int) -> dict:
    return {"item": item_id, "qty": qty, "status": "placed"}
