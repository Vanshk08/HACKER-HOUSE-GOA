"""
Tests for the 5 Restored Investigation Tools.

Verifies that:
1. Each tool is registered in tools/__init__.py and tools.INVESTIGATION_TOOLS.
2. Each tool is a LangChain tool invocable by the agent.
3. Each tool executes successfully without throwing exceptions.
4. Each tool queries real DuckDB / HHGOA dataset records.
5. Each tool returns structured evidence with observed data and derived calculations.
6. No hardcoded unavailable stub remains.
"""

import unittest
from tools import (
    INVESTIGATION_TOOLS,
    get_connected_cards,
    get_device_connections,
    get_customer_device_history,
    find_shared_origins,
    find_related_fraud,
)


class TestRestoredTools(unittest.TestCase):
    """Test suite for the 5 restored investigation tools."""

    def test_registration_in_investigation_tools(self):
        """Verify all 5 tools are in INVESTIGATION_TOOLS."""
        tool_names = [t.name for t in INVESTIGATION_TOOLS]
        self.assertIn("get_connected_cards", tool_names)
        self.assertIn("get_device_connections", tool_names)
        self.assertIn("get_customer_device_history", tool_names)
        self.assertIn("find_shared_origins", tool_names)
        self.assertIn("find_related_fraud", tool_names)

    def test_get_connected_cards_executes_with_real_data(self):
        """Verify get_connected_cards queries real data and returns structured evidence."""
        # C03528-K1 has connected cards in closed_cases_history
        result = get_connected_cards.invoke({"card_id": "C03528-K1"})
        
        self.assertIsInstance(result, dict)
        self.assertNotIn("unavailable_data", result)
        self.assertEqual(result.get("card_id"), "C03528-K1")
        self.assertIn("connected_card_ids", result)
        self.assertIn("connections", result)
        self.assertIn("derived_calculations", result)
        self.assertTrue(len(result["connected_card_ids"]) > 0)
        self.assertEqual(result.get("backend_status"), "hhgoa_ieee")

    def test_get_connected_cards_nonexistent(self):
        """Verify get_connected_cards handles a card with no connections cleanly."""
        result = get_connected_cards.invoke({"card_id": "NONEXISTENT-CARD-999"})
        self.assertIsInstance(result, dict)
        self.assertNotIn("unavailable_data", result)
        self.assertEqual(result.get("connected_card_ids"), [])
        self.assertEqual(result.get("backend_status"), "hhgoa_ieee")

    def test_get_device_connections_executes_with_real_data(self):
        """Verify get_device_connections returns real device connection topology."""
        result = get_device_connections.invoke({"customer_id": "C12382"})
        
        self.assertIsInstance(result, dict)
        self.assertNotIn("unavailable_data", result)
        self.assertIn("associated_customers", result)
        self.assertIn("associated_transactions", result)
        self.assertIn("observed_devices", result)
        self.assertIn("derived_calculations", result)
        self.assertEqual(result.get("backend_status"), "hhgoa_ieee")

    def test_get_customer_device_history_executes_with_real_data(self):
        """Verify get_customer_device_history retrieves historical device usage from real data."""
        result = get_customer_device_history.invoke({"customer_id": "C12382"})
        
        self.assertIsInstance(result, dict)
        self.assertNotIn("unavailable_data", result)
        self.assertEqual(result.get("customer_id"), "C12382")
        self.assertIn("devices", result)
        self.assertIn("derived_calculations", result)
        self.assertEqual(result.get("backend_status"), "hhgoa_ieee")

    def test_find_shared_origins_executes_with_real_data(self):
        """Verify find_shared_origins detects shared email domains / regions without stub."""
        result = find_shared_origins.invoke({"customer_id": "C12382"})
        
        self.assertIsInstance(result, dict)
        self.assertNotIn("unavailable_data", result)
        self.assertIn("shared_origins", result)
        self.assertIn("derived_calculations", result)
        # C12382 has transactions with gmail.com and addr1=299.0
        shared = result.get("shared_origins", [])
        self.assertTrue(len(shared) > 0)
        origin_types = [s.get("entity_type") for s in shared]
        self.assertTrue("EmailDomain" in origin_types or "BillingRegion" in origin_types)
        self.assertEqual(result.get("backend_status"), "hhgoa_ieee")

    def test_find_related_fraud_executes_with_real_data(self):
        """Verify find_related_fraud queries closed fraud cases without stub."""
        # Query with region '299.0' or customer_id
        result = find_related_fraud.invoke({"region": "299.0"})
        
        self.assertIsInstance(result, dict)
        self.assertNotIn("unavailable_data", result)
        self.assertIn("related_fraud_cases", result)
        self.assertIn("derived_calculations", result)
        self.assertEqual(result.get("backend_status"), "hhgoa_ieee")


if __name__ == "__main__":
    unittest.main()
