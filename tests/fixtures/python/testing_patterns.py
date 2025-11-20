"""
Realistic testing patterns fixture - E-commerce order processing system.

This represents a real-world test suite for an e-commerce platform with:
- Complex test hierarchies with shared fixtures
- Integration tests with database setup/teardown
- Property-based tests with realistic business rules
- Mock patterns for external services (payment, shipping)
- Parametrized tests for edge cases
- Pytest hooks for test environment management
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Optional


# ============================================================================
# DOMAIN MODELS (for testing context)
# ============================================================================

class Order:
    def __init__(self, order_id: str, customer_id: str, items: list[dict],
                 discount_code: str | None = None):
        self.order_id = order_id
        self.customer_id = customer_id
        self.items = items
        self.discount_code = discount_code
        self.status = 'pending'
        self.total = self._calculate_total()

    def _calculate_total(self) -> Decimal:
        subtotal = sum(Decimal(str(item['price'])) * item['quantity'] for item in self.items)
        if self.discount_code:
            discount = self._apply_discount(subtotal)
            return subtotal - discount
        return subtotal

    def _apply_discount(self, subtotal: Decimal) -> Decimal:
        # Discount logic here
        return Decimal('0')


class PaymentProcessor:
    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.endpoint = endpoint

    def charge(self, amount: Decimal, payment_method: str) -> dict:
        # External payment API call
        raise NotImplementedError("Must mock in tests")

    def refund(self, transaction_id: str, amount: Decimal) -> bool:
        raise NotImplementedError("Must mock in tests")


class InventoryService:
    def __init__(self, db_connection):
        self.db = db_connection

    def check_availability(self, product_id: str, quantity: int) -> bool:
        # Database check
        raise NotImplementedError("Must mock in tests")

    def reserve_stock(self, product_id: str, quantity: int, order_id: str) -> bool:
        raise NotImplementedError("Must mock in tests")

    def release_stock(self, order_id: str) -> None:
        raise NotImplementedError("Must mock in tests")


class ShippingService:
    def create_shipment(self, order: Order, address: dict) -> str:
        raise NotImplementedError("Must mock in tests")

    def track_shipment(self, tracking_number: str) -> dict:
        raise NotImplementedError("Must mock in tests")


class OrderProcessor:
    def __init__(self, payment: PaymentProcessor, inventory: InventoryService,
                 shipping: ShippingService):
        self.payment = payment
        self.inventory = inventory
        self.shipping = shipping

    def process_order(self, order: Order, payment_method: str,
                     shipping_address: dict) -> dict:
        # Check inventory
        for item in order.items:
            if not self.inventory.check_availability(item['product_id'], item['quantity']):
                return {'success': False, 'error': 'Out of stock', 'item': item['product_id']}

        # Reserve stock
        for item in order.items:
            if not self.inventory.reserve_stock(item['product_id'], item['quantity'], order.order_id):
                self.inventory.release_stock(order.order_id)
                return {'success': False, 'error': 'Failed to reserve stock'}

        # Charge payment
        try:
            charge_result = self.payment.charge(order.total, payment_method)
            if not charge_result.get('success'):
                self.inventory.release_stock(order.order_id)
                return {'success': False, 'error': 'Payment failed'}
        except Exception as e:
            self.inventory.release_stock(order.order_id)
            return {'success': False, 'error': f'Payment error: {str(e)}'}

        # Create shipment
        try:
            tracking = self.shipping.create_shipment(order, shipping_address)
            order.status = 'confirmed'
            return {
                'success': True,
                'order_id': order.order_id,
                'transaction_id': charge_result.get('transaction_id'),
                'tracking_number': tracking
            }
        except Exception as e:
            self.payment.refund(charge_result.get('transaction_id'), order.total)
            self.inventory.release_stock(order.order_id)
            return {'success': False, 'error': f'Shipping error: {str(e)}'}


# ============================================================================
# UNITTEST TEST SUITE WITH COMPLEX SETUP/TEARDOWN
# ============================================================================

class OrderProcessingTestBase(unittest.TestCase):
    """Base test class with shared fixtures and helpers."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data for all tests."""
        cls.test_products = {
            'PROD001': {'name': 'Laptop', 'price': Decimal('999.99'), 'stock': 10},
            'PROD002': {'name': 'Mouse', 'price': Decimal('29.99'), 'stock': 50},
            'PROD003': {'name': 'Keyboard', 'price': Decimal('79.99'), 'stock': 25},
        }
        cls.test_customer_id = 'CUST12345'
        cls.valid_payment_method = 'card_visa_1234'
        cls.valid_shipping_address = {
            'street': '123 Main St',
            'city': 'San Francisco',
            'state': 'CA',
            'zip': '94102',
            'country': 'US'
        }

    def setUp(self):
        """Set up fresh mocks for each test."""
        self.mock_payment = Mock(spec=PaymentProcessor)
        self.mock_inventory = Mock(spec=InventoryService)
        self.mock_shipping = Mock(spec=ShippingService)

        self.processor = OrderProcessor(
            payment=self.mock_payment,
            inventory=self.mock_inventory,
            shipping=self.mock_shipping
        )

        # Default successful mock behaviors
        self.mock_inventory.check_availability.return_value = True
        self.mock_inventory.reserve_stock.return_value = True
        self.mock_payment.charge.return_value = {
            'success': True,
            'transaction_id': 'TXN123456'
        }
        self.mock_shipping.create_shipment.return_value = 'TRACK123456'

    def tearDown(self):
        """Clean up after each test."""
        self.mock_payment.reset_mock()
        self.mock_inventory.reset_mock()
        self.mock_shipping.reset_mock()

    def create_test_order(self, items=None, discount_code=None):
        """Helper to create test orders."""
        if items is None:
            items = [
                {'product_id': 'PROD001', 'quantity': 1, 'price': 999.99},
                {'product_id': 'PROD002', 'quantity': 2, 'price': 29.99}
            ]
        return Order(
            order_id=f'ORD{datetime.now().timestamp()}',
            customer_id=self.test_customer_id,
            items=items,
            discount_code=discount_code
        )


class TestSuccessfulOrderFlow(OrderProcessingTestBase):
    """Test successful order processing scenarios."""

    def test_single_item_order_success(self):
        """Test processing order with single item."""
        order = self.create_test_order(items=[
            {'product_id': 'PROD001', 'quantity': 1, 'price': 999.99}
        ])

        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        # Assert successful result
        self.assertTrue(result['success'])
        self.assertIn('order_id', result)
        self.assertIn('transaction_id', result)
        self.assertIn('tracking_number', result)
        self.assertEqual(result['transaction_id'], 'TXN123456')
        self.assertEqual(result['tracking_number'], 'TRACK123456')

        # Verify service interactions
        self.mock_inventory.check_availability.assert_called_once_with('PROD001', 1)
        self.mock_inventory.reserve_stock.assert_called_once_with('PROD001', 1, order.order_id)
        self.mock_payment.charge.assert_called_once_with(order.total, self.valid_payment_method)
        self.mock_shipping.create_shipment.assert_called_once_with(order, self.valid_shipping_address)

        # Verify no rollback calls
        self.mock_inventory.release_stock.assert_not_called()
        self.mock_payment.refund.assert_not_called()

    def test_multi_item_order_with_discount(self):
        """Test processing order with multiple items and discount code."""
        items = [
            {'product_id': 'PROD001', 'quantity': 2, 'price': 999.99},
            {'product_id': 'PROD002', 'quantity': 3, 'price': 29.99},
            {'product_id': 'PROD003', 'quantity': 1, 'price': 79.99}
        ]
        order = self.create_test_order(items=items, discount_code='SAVE20')

        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        self.assertTrue(result['success'])

        # Verify all items were checked
        self.assertEqual(self.mock_inventory.check_availability.call_count, 3)
        self.assertEqual(self.mock_inventory.reserve_stock.call_count, 3)

        # Verify call order
        expected_calls = [
            call('PROD001', 2, order.order_id),
            call('PROD002', 3, order.order_id),
            call('PROD003', 1, order.order_id)
        ]
        self.mock_inventory.reserve_stock.assert_has_calls(expected_calls, any_order=False)


class TestInventoryFailures(OrderProcessingTestBase):
    """Test order processing with inventory failures."""

    def test_out_of_stock_first_item(self):
        """Test order fails when first item is out of stock."""
        self.mock_inventory.check_availability.return_value = False

        order = self.create_test_order()
        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Out of stock')
        self.assertIn('item', result)

        # Should not proceed to payment or shipping
        self.mock_payment.charge.assert_not_called()
        self.mock_shipping.create_shipment.assert_not_called()

    def test_stock_reservation_fails_triggers_rollback(self):
        """Test that failed stock reservation releases all reserved stock."""
        # First item succeeds, second fails
        self.mock_inventory.reserve_stock.side_effect = [True, False]

        items = [
            {'product_id': 'PROD001', 'quantity': 1, 'price': 999.99},
            {'product_id': 'PROD002', 'quantity': 2, 'price': 29.99}
        ]
        order = self.create_test_order(items=items)

        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Failed to reserve stock')

        # Verify rollback was called
        self.mock_inventory.release_stock.assert_called_once_with(order.order_id)

        # Should not proceed to payment
        self.mock_payment.charge.assert_not_called()


class TestPaymentFailures(OrderProcessingTestBase):
    """Test order processing with payment failures."""

    def test_payment_declined_releases_inventory(self):
        """Test that declined payment releases reserved inventory."""
        self.mock_payment.charge.return_value = {
            'success': False,
            'error': 'Card declined'
        }

        order = self.create_test_order()
        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Payment failed')

        # Verify inventory was reserved then released
        self.mock_inventory.reserve_stock.assert_called()
        self.mock_inventory.release_stock.assert_called_once_with(order.order_id)

        # Verify no shipment created
        self.mock_shipping.create_shipment.assert_not_called()

    def test_payment_exception_triggers_full_rollback(self):
        """Test that payment exception triggers complete rollback."""
        self.mock_payment.charge.side_effect = Exception("Network timeout")

        order = self.create_test_order()
        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        self.assertFalse(result['success'])
        self.assertIn('Payment error', result['error'])
        self.assertIn('Network timeout', result['error'])

        # Verify rollback
        self.mock_inventory.release_stock.assert_called_once()


class TestShippingFailures(OrderProcessingTestBase):
    """Test order processing with shipping failures."""

    def test_shipping_failure_refunds_payment_and_releases_inventory(self):
        """Test that shipping failure triggers full rollback including refund."""
        self.mock_shipping.create_shipment.side_effect = Exception("Invalid address")

        order = self.create_test_order()
        result = self.processor.process_order(
            order,
            self.valid_payment_method,
            self.valid_shipping_address
        )

        self.assertFalse(result['success'])
        self.assertIn('Shipping error', result['error'])

        # Verify payment was charged then refunded
        self.mock_payment.charge.assert_called_once()
        self.mock_payment.refund.assert_called_once_with('TXN123456', order.total)

        # Verify inventory was released
        self.mock_inventory.release_stock.assert_called_once_with(order.order_id)


# ============================================================================
# PROPERTY-BASED TESTS WITH HYPOTHESIS
# ============================================================================

# Custom strategies for realistic business data
@composite
def product_strategy(draw):
    """Generate realistic product data."""
    return {
        'product_id': f"PROD{draw(st.integers(min_value=1000, max_value=9999))}",
        'quantity': draw(st.integers(min_value=1, max_value=10)),
        'price': float(draw(st.decimals(min_value=1, max_value=9999, places=2)))
    }

@composite
def order_items_strategy(draw):
    """Generate realistic order items."""
    num_items = draw(st.integers(min_value=1, max_value=5))
    items = [draw(product_strategy()) for _ in range(num_items)]
    # Ensure unique product IDs
    seen = set()
    unique_items = []
    for item in items:
        if item['product_id'] not in seen:
            seen.add(item['product_id'])
            unique_items.append(item)
    return unique_items if unique_items else [draw(product_strategy())]

@composite
def address_strategy(draw):
    """Generate realistic US addresses."""
    return {
        'street': f"{draw(st.integers(min_value=1, max_value=9999))} {draw(st.sampled_from(['Main', 'Oak', 'Pine', 'Elm']))} St",
        'city': draw(st.sampled_from(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'])),
        'state': draw(st.sampled_from(['NY', 'CA', 'IL', 'TX', 'AZ'])),
        'zip': f"{draw(st.integers(min_value=10000, max_value=99999))}",
        'country': 'US'
    }


class TestOrderBusinessRules(unittest.TestCase):
    """Property-based tests for order business rules."""

    @given(order_items_strategy())
    def test_order_total_is_sum_of_items(self, items):
        """Property: Order total equals sum of (price * quantity) for all items."""
        order = Order(
            order_id='TEST_ORD',
            customer_id='TEST_CUST',
            items=items,
            discount_code=None
        )

        expected_total = sum(Decimal(str(item['price'])) * item['quantity'] for item in items)
        self.assertEqual(order.total, expected_total)
        assert order.total >= 0  # Total should never be negative

    @given(order_items_strategy(), st.text(min_size=5, max_size=20))
    def test_order_with_any_discount_code_validates(self, items, discount_code):
        """Property: Order accepts any discount code without crashing."""
        assume(len(items) > 0)  # Ensure we have items

        order = Order(
            order_id='TEST_ORD',
            customer_id='TEST_CUST',
            items=items,
            discount_code=discount_code
        )

        self.assertIsNotNone(order.total)
        self.assertGreaterEqual(order.total, Decimal('0'))

    @given(st.integers(min_value=1, max_value=100), st.decimals(min_value=1, max_value=999, places=2))
    def test_item_subtotal_equals_price_times_quantity(self, quantity, price):
        """Property: Item subtotal is always price * quantity."""
        items = [{'product_id': 'TEST', 'quantity': quantity, 'price': float(price)}]
        order = Order('ORD1', 'CUST1', items)

        expected = Decimal(str(price)) * quantity
        self.assertEqual(order.total, expected)


# ============================================================================
# PYTEST HOOKS AND FIXTURES
# ============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: marks integration tests requiring database")
    config.addinivalue_line("markers", "slow: marks slow-running tests")
    config.addinivalue_line("markers", "external_service: requires external service availability")
    config.addinivalue_line("markers", "payment: payment processing tests")
    config.addinivalue_line("markers", "inventory: inventory management tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    skip_integration = pytest.mark.skip(reason="Integration tests disabled")

    for item in items:
        if "integration" in item.keywords and not config.getoption("--run-integration", default=False):
            item.add_marker(skip_integration)

        # Add slow marker to integration tests automatically
        if "external_service" in item.keywords:
            item.add_marker(pytest.mark.slow)


def pytest_runtest_setup(item):
    """Setup before each test."""
    if "integration" in item.keywords:
        # Setup database connection
        pass


def pytest_runtest_teardown(item, nextitem):
    """Teardown after each test."""
    if "integration" in item.keywords:
        # Cleanup database
        pass


@pytest.fixture(scope="session")
def database_connection():
    """Session-scoped database connection."""
    conn = Mock()  # In real tests, this would be actual DB connection
    conn.execute = Mock(return_value=[])
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def clean_database(database_connection):
    """Function-scoped fixture to ensure clean database state."""
    # Truncate tables before test
    database_connection.execute("TRUNCATE orders, order_items, customers")
    yield database_connection
    # Cleanup after test
    database_connection.execute("TRUNCATE orders, order_items, customers")


@pytest.fixture
def payment_service():
    """Fixture for mocked payment service."""
    service = Mock(spec=PaymentProcessor)
    service.charge.return_value = {'success': True, 'transaction_id': 'TXN_MOCK'}
    return service


@pytest.fixture
def inventory_service():
    """Fixture for mocked inventory service."""
    service = Mock(spec=InventoryService)
    service.check_availability.return_value = True
    service.reserve_stock.return_value = True
    return service


# ============================================================================
# PYTEST PARAMETRIZE TESTS
# ============================================================================

@pytest.mark.parametrize("quantity,price,expected_subtotal", [
    (1, Decimal('10.00'), Decimal('10.00')),
    (2, Decimal('15.50'), Decimal('31.00')),
    (5, Decimal('99.99'), Decimal('499.95')),
    (10, Decimal('100.00'), Decimal('1000.00')),
])
def test_order_item_subtotal_calculation(quantity, price, expected_subtotal):
    """Test subtotal calculation with various quantities and prices."""
    items = [{'product_id': 'TEST', 'quantity': quantity, 'price': float(price)}]
    order = Order('ORD1', 'CUST1', items)
    assert order.total == expected_subtotal


@pytest.mark.parametrize("items,expected_item_count", [
    ([{'product_id': 'P1', 'quantity': 1, 'price': 10.0}], 1),
    ([{'product_id': 'P1', 'quantity': 2, 'price': 10.0},
      {'product_id': 'P2', 'quantity': 1, 'price': 20.0}], 2),
    ([{'product_id': f'P{i}', 'quantity': 1, 'price': 10.0} for i in range(5)], 5),
])
def test_order_item_count(items, expected_item_count):
    """Test that order contains expected number of items."""
    order = Order('ORD1', 'CUST1', items)
    assert len(order.items) == expected_item_count


if __name__ == "__main__":
    unittest.main()
