"""inventory public surface."""
_STOCK: dict[str, int] = {}

def decrement_stock(item_id: str, qty: int) -> int:
    _STOCK[item_id] = _STOCK.get(item_id, 0) - qty
    return _STOCK[item_id]
