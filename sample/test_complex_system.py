import unittest

from sample.complex_system import ProductCatalog, Inventory, Order


class TestComplexSystem(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ProductCatalog({"A": 500, "B": 1200})
        self.inventory = Inventory({"A": 5, "B": 2})

    def test_reserve_and_commit(self) -> None:
        order = Order(self.catalog, self.inventory)
        order.add_item("A", 2)
        order.add_item("B", 1)
        order.reserve()
        self.assertEqual(self.inventory.available("A"), 3)
        self.assertEqual(self.inventory.available("B"), 1)
        order.commit()
        self.assertEqual(self.inventory.on_hand("A"), 3)
        self.assertEqual(self.inventory.on_hand("B"), 1)

    def test_reserve_rolls_back_on_failure(self) -> None:
        order = Order(self.catalog, self.inventory)
        order.add_item("A", 3)
        order.add_item("B", 3)  # B has only 2 in stock
        with self.assertRaises(ValueError):
            order.reserve()
        self.assertEqual(self.inventory.available("A"), 5)
        self.assertEqual(self.inventory.available("B"), 2)

    def test_total_with_discount_and_tax(self) -> None:
        order = Order(self.catalog, self.inventory)
        order.add_item("A", 2)  # 1000
        order.add_item("B", 1)  # 1200
        # subtotal 2200, discount 10% => 220, taxable 1980, tax 5% => 99
        self.assertEqual(order.total_cents(discount_pct=10, tax_rate_pct=5), 2079)


if __name__ == "__main__":
    unittest.main()
