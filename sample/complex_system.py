from __future__ import annotations


class ProductCatalog:
    def __init__(self, products: dict[str, int]) -> None:
        # products: sku -> price_cents
        self._products = dict(products)

    def has(self, sku: str) -> bool:
        return sku in self._products

    def price_cents(self, sku: str) -> int:
        if sku not in self._products:
            raise KeyError(f"Unknown SKU: {sku}")
        return self._products[sku]


class Inventory:
    def __init__(self, on_hand: dict[str, int]) -> None:
        self._on_hand = dict(on_hand)
        self._reserved: dict[str, int] = {}

    def available(self, sku: str) -> int:
        return self._on_hand.get(sku, 0) - self._reserved.get(sku, 0)

    def reserve(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        if self.available(sku) < qty:
            raise ValueError(f"Insufficient stock for {sku}")
        self._reserved[sku] = self._reserved.get(sku, 0) + qty

    def release(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        current = self._reserved.get(sku, 0)
        if current < qty:
            raise ValueError("Cannot release more than reserved")
        remaining = current - qty
        if remaining:
            self._reserved[sku] = remaining
        else:
            self._reserved.pop(sku, None)

    def commit(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        current = self._reserved.get(sku, 0)
        if current < qty:
            raise ValueError("Cannot commit more than reserved")
        self._on_hand[sku] = self._on_hand.get(sku, 0) - qty
        self.release(sku, qty)

    def on_hand(self, sku: str) -> int:
        return self._on_hand.get(sku, 0)


class Order:
    def __init__(self, catalog: ProductCatalog, inventory: Inventory) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._inventory = inventory
        self._items: dict[str, int] = {}

    def add_item(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        if not self._catalog.has(sku):
            raise KeyError(f"Unknown SKU: {sku}")
        self._items[sku] = self._items.get(sku, 0) + qty

    def remove_item(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        current = self._items.get(sku, 0)
        if current < qty:
            raise ValueError("Cannot remove more than ordered")
        remaining = current - qty
        if remaining:
            self._items[sku] = remaining
        else:
            self._items.pop(sku, None)

    def reserve(self) -> None:
        reserved: list[tuple[str, int]] = []
        try:
            for sku, qty in self._items.items():
                self._inventory.reserve(sku, qty)
                reserved.append((sku, qty))
        except Exception:
            for sku, qty in reserved:
                self._inventory.release(sku, qty)
            raise

    def commit(self) -> None:
        for sku, qty in self._items.items():
            self._inventory.commit(sku, qty)

    def subtotal_cents(self) -> int:
        total = 0
        for sku, qty in self._items.items():
            total += self._catalog.price_cents(sku) * qty
        return total

    def total_cents(self, discount_pct: int = 0, tax_rate_pct: int = 0) -> int:
        if not (0 <= discount_pct <= 100):
            raise ValueError("discount_pct must be 0-100")
        if not (0 <= tax_rate_pct <= 100):
            raise ValueError("tax_rate_pct must be 0-100")
        subtotal = self.subtotal_cents()
        discount = (subtotal * discount_pct) // 100
        taxable = subtotal - discount
        tax = (taxable * tax_rate_pct) // 100
        return taxable + tax
