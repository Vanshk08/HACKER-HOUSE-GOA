"""
Comprehensive test suite for Real LLM Agent upgrade.
Tests:
1. Provider configuration (OpenAI, Anthropic, Mock, missing key rejection, no silent fallback).
2. Tool-call parsing and execution via ToolExecutor.
3. Structured assessment adhering to 9-field schema.
4. Independent fraud_probability calculation (not copied from risk_score).
5. Customer-report semantics (customer_report != customer denied, response status unknown).
6. Policy enforcement (deterministic R1-R10 rules, LLM cannot decide policy actions).
7. Fabricated transaction ID rejection (validation against real dataset and verified exposure calculation).
8. Dynamic tool selection across multiple cycles.
9. Mock mode offline execution.
"""

import os
import sys
import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage, HumanMessage

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.llm_config import get_llm_config, LLMConfig
from agent.llm_engine import (
    AutonomousInvestigatorLLM,
    AutonomousAssessmentLLM,
    MockInvestigatorLLM,
    MockAssessmentLLM,
    get_investigator_llm,
    get_assessment_llm,
)
from agent.investigator import InvestigationAgent
from agent.tool_executor import ToolExecutor
from agent.assessment import AssessmentAgent, AssessmentSchema
from agent.orchestrator import build_investigation_graph
from agent.state import create_initial_state
from config.policy import evaluate_policy
from tools.data_store import DataStore


class TestRealLLMAgent(unittest.TestCase):

    def setUp(self):
        self.orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    # ----------------------------------------------------------------------
    # 1. PROVIDER CONFIGURATION TESTS
    # ----------------------------------------------------------------------
    def test_provider_configuration_mock(self):
        """Test explicit mock provider selection."""
        os.environ["LLM_PROVIDER"] = "mock"
        cfg = get_llm_config()
        self.assertEqual(cfg.provider, "mock")
        self.assertEqual(cfg.model, "mock-investigator-v1")
        self.assertIsNone(cfg.api_key)

    def test_provider_configuration_openai_with_key(self):
        """Test openai provider when API key is present."""
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-12345"
        os.environ["OPENAI_MODEL"] = "gpt-4o-mini"
        cfg = get_llm_config()
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-4o-mini")
        self.assertEqual(cfg.api_key, "sk-test-fake-key-12345")

    def test_provider_configuration_openai_missing_key_raises(self):
        """Test that missing OpenAI API key raises and does NOT silently fall back to mock."""
        os.environ["LLM_PROVIDER"] = "openai"
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        with self.assertRaises(ValueError) as ctx:
            get_llm_config()
        self.assertIn("OPENAI_API_KEY is missing", str(ctx.exception))
        self.assertIn("Silent fallback to mock is prohibited", str(ctx.exception))

    def test_provider_configuration_anthropic_with_key(self):
        """Test anthropic provider when API key is present."""
        os.environ["LLM_PROVIDER"] = "anthropic"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-fake-key"
        os.environ["ANTHROPIC_MODEL"] = "claude-3-5-sonnet-20241022"
        cfg = get_llm_config()
        self.assertEqual(cfg.provider, "anthropic")
        self.assertEqual(cfg.model, "claude-3-5-sonnet-20241022")
        self.assertEqual(cfg.api_key, "sk-ant-test-fake-key")

    def test_provider_configuration_anthropic_missing_key_raises(self):
        """Test that missing Anthropic API key raises and does NOT silently fall back to mock."""
        os.environ["LLM_PROVIDER"] = "anthropic"
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        with self.assertRaises(ValueError) as ctx:
            get_llm_config()
        self.assertIn("ANTHROPIC_API_KEY is missing", str(ctx.exception))
        self.assertIn("Silent fallback to mock is prohibited", str(ctx.exception))

    def test_provider_configuration_unset_raises(self):
        """Test that unset LLM_PROVIDER raises ValueError and never silently defaults to mock."""
        if "LLM_PROVIDER" in os.environ:
            del os.environ["LLM_PROVIDER"]

        with self.assertRaises(ValueError) as ctx:
            get_llm_config()
        self.assertIn("LLM_PROVIDER environment variable is not set", str(ctx.exception))

    def test_provider_configuration_invalid_provider_raises(self):
        """Test that unsupported provider raises ValueError."""
        os.environ["LLM_PROVIDER"] = "unknown_provider_xyz"
        with self.assertRaises(ValueError) as ctx:
            get_llm_config()
        self.assertIn("Unsupported LLM_PROVIDER", str(ctx.exception))

    # ----------------------------------------------------------------------
    # 2. TOOL-CALL PARSING AND EXECUTION TESTS
    # ----------------------------------------------------------------------
    def test_tool_call_parsing_and_execution(self):
        """Test that ToolExecutor correctly executes LLM tool calls against real data."""
        executor = ToolExecutor()
        tool_call = {
            "name": "get_transaction",
            "args": {"transaction_id": "3514030"},
            "id": "call_test_001",
        }
        res = executor.execute(tool_call)

        self.assertEqual(res["tool"], "get_transaction")
        self.assertEqual(res["tool_call_id"], "call_test_001")
        self.assertIn("result", res)
        self.assertEqual(res["result"]["transaction_id"], "3514030")
        self.assertEqual(res["result"]["customer_id"], "C12382")
        self.assertEqual(res["result"]["amount"], 77.07)

        # Verify evidence transformation
        ev = res["evidence"]
        self.assertEqual(ev["source"], "get_transaction")
        self.assertEqual(ev["type"], "tool_result")
        self.assertEqual(ev["data"]["result"]["channel"], "in_person")

        # Verify tool message
        msg = res["message"]
        self.assertEqual(msg.tool_call_id, "call_test_001")
        self.assertIn("3514030", msg.content)

    def test_unknown_tool_call_raises(self):
        """Test that unknown tool name raises ValueError."""
        executor = ToolExecutor()
        with self.assertRaises(ValueError):
            executor.execute({"name": "non_existent_tool", "args": {}, "id": "1"})

    # ----------------------------------------------------------------------
    # 3. STRUCTURED ASSESSMENT TESTS
    # ----------------------------------------------------------------------
    def test_structured_assessment_9_fields(self):
        """Test that AssessmentAgent produces all 9 required schema fields."""
        class MockLLM:
            def invoke(self, messages):
                return {
                    "verdict": "uncertain",
                    "fraud_probability": 0.45,
                    "fraud_type": None,
                    "exposure": 77.07,
                    "affected_txn_ids": ["3514030"],
                    "supporting_evidence": ["Risk score 0.61"],
                    "contradicting_evidence": ["Historical repeat transactions in region 444"],
                    "reasoning": "Evidence is inconclusive without direct customer validation.",
                    "confidence": 0.60,
                }

        agent = AssessmentAgent(MockLLM())
        state = create_initial_state("HHG-001", "C12382", "C12382-K1", "3514030", risk_score=0.61)
        res = agent.node(state)

        ass = res["assessment"]
        required_fields = [
            "verdict",
            "fraud_probability",
            "fraud_type",
            "exposure",
            "affected_txn_ids",
            "supporting_evidence",
            "contradicting_evidence",
            "reasoning",
            "confidence",
        ]
        for f in required_fields:
            self.assertIn(f, ass, f"Missing field {f} in assessment")

        self.assertIn(ass["verdict"], ["confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"])
        self.assertTrue(0.0 <= ass["fraud_probability"] <= 1.0)
        self.assertTrue(0.0 <= ass["confidence"] <= 1.0)
        self.assertEqual(ass["affected_txn_ids"], ["3514030"])
        self.assertEqual(ass["exposure"], 77.07)

    # ----------------------------------------------------------------------
    # 4. INDEPENDENT FRAUD PROBABILITY TESTS
    # ----------------------------------------------------------------------
    def test_independent_fraud_probability_not_copied_from_risk_score(self):
        """Test that fraud_probability is independent and not copied from case-pack risk_score."""
        class CopyingLLM:
            def invoke(self, messages):
                # Simulated model attempting to copy risk_score directly
                return {
                    "verdict": "uncertain",
                    "fraud_probability": 0.61,  # Exact copy of trigger risk_score
                    "exposure": 77.07,
                    "affected_txn_ids": ["3514030"],
                    "reasoning": "Assessing based on risk score.",
                }

        agent = AssessmentAgent(CopyingLLM())
        state = create_initial_state("HHG-001", "C12382", "C12382-K1", "3514030", risk_score=0.61)
        res = agent.node(state)

        ass = res["assessment"]
        # Must NOT be 0.61
        self.assertNotEqual(ass["fraud_probability"], 0.61)
        self.assertTrue(0.0 <= ass["fraud_probability"] <= 1.0)

    # ----------------------------------------------------------------------
    # 5. CUSTOMER REPORT SEMANTICS TESTS
    # ----------------------------------------------------------------------
    def test_customer_report_semantics_unknown_status(self):
        """
        A case trigger such as customer_report does NOT mean the customer denied fraud.
        customer_response_status must remain 'unknown'.
        """
        state = create_initial_state(
            case_id="HHG-004",
            customer_id="C1004",
            card_id="C1004-K1",
            flagged_txn_id="3514030",
            trigger_type="customer_report",
            trigger_text="Customer reported unauthorized charge: never made this transaction",
            risk_score=0.35,
        )

        # Initial customer_response_status must be 'unknown'
        self.assertEqual(state["customer_response_status"], "unknown")

        # Run policy evaluation
        decision = evaluate_policy(state)

        # customer_response_status must remain 'unknown'
        self.assertEqual(decision["customer_response_status"], "unknown")

        # Rule R2 (Customer Denial) must NOT match because status is unknown, NOT denied
        self.assertNotIn("R2", decision["matched_rules"])

        # BLOCK_CARD must NOT be triggered via customer denial
        self.assertNotIn("BLOCK_CARD", decision["actions"])

    # ----------------------------------------------------------------------
    # 6. POLICY ENFORCEMENT TESTS
    # ----------------------------------------------------------------------
    def test_policy_engine_deterministic_enforcement(self):
        """
        Verify the Policy Engine deterministically decides actions.
        The LLM does not decide actions.
        """
        state = {
            "case_id": "HHG-001",
            "customer_id": "C12382",
            "card_id": "C12382-K1",
            "flagged_txn_id": "3514030",
            "assessment": {
                "verdict": "uncertain",
                "fraud_probability": 0.42,
                "exposure": 77.07,
                "affected_txn_ids": ["3514030"],
                "reasoning": "The LLM erroneously suggests BLOCK_CARD.",  # LLM text should NOT dictate policy
            },
            "customer_response_status": "unknown",
            "evidence_requests": [{"request_type": "customer_confirmation"}],
        }

        decision = evaluate_policy(state)

        # Deterministic R1 matches (< 0.70, unconfirmed risk)
        self.assertIn("R1", decision["matched_rules"])
        self.assertIn("VERIFY_WITH_CUSTOMER", decision["actions"])
        # Punitive action BLOCK_CARD must NOT be present
        self.assertNotIn("BLOCK_CARD", decision["actions"])

    # ----------------------------------------------------------------------
    # 7. FABRICATED TRANSACTION ID REJECTION & EXPOSURE TESTS
    # ----------------------------------------------------------------------
    def test_fabricated_transaction_id_rejection(self):
        """
        Validate every affected transaction ID against actual dataset.
        Reject fabricated transaction IDs and calculate exposure ONLY from verified IDs.
        """
        class FabricatingLLM:
            def invoke(self, messages):
                return {
                    "verdict": "suspected_fraud",
                    "fraud_probability": 0.75,
                    "fraud_type": "card_cloning",
                    "exposure": 99999.00,  # Fabricated exposure
                    "affected_txn_ids": [
                        "3514030",          # Real verified transaction ($77.07)
                        "999999999",        # Fabricated transaction ID
                        "FAKE_TXN_HALLUC",  # Fabricated transaction ID
                    ],
                    "supporting_evidence": ["Suspicious activity"],
                    "contradicting_evidence": [],
                    "reasoning": "Multiple fraudulent transactions identified.",
                    "confidence": 0.70,
                }

        agent = AssessmentAgent(FabricatingLLM())
        state = create_initial_state("HHG-001", "C12382", "C12382-K1", "3514030", risk_score=0.61)
        res = agent.node(state)

        ass = res["assessment"]

        # Only real transaction 3514030 must survive
        self.assertEqual(ass["affected_txn_ids"], ["3514030"])
        self.assertNotIn("999999999", ass["affected_txn_ids"])
        self.assertNotIn("FAKE_TXN_HALLUC", ass["affected_txn_ids"])

        # Exposure must be calculated strictly from verified transaction amount ($77.07)
        self.assertAlmostEqual(ass["exposure"], 77.07, places=2)
        self.assertNotEqual(ass["exposure"], 99999.00)

        # Reasoning should mention rejected fabricated transaction IDs
        self.assertIn("Rejected", ass["reasoning"])

    # ----------------------------------------------------------------------
    # 8. DYNAMIC TOOL SELECTION TESTS
    # ----------------------------------------------------------------------
    def test_dynamic_tool_selection_multi_cycle(self):
        """Test multi-cycle dynamic tool selection by investigator."""
        class DynamicLLM:
            def __init__(self):
                self.calls = 0

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.calls += 1
                if self.calls == 1:
                    return AIMessage(
                        content="Examining flagged transaction first.",
                        tool_calls=[{"name": "get_transaction", "args": {"transaction_id": "3514030"}, "id": "c1"}]
                    )
                elif self.calls == 2:
                    return AIMessage(
                        content="Transaction is in region 444. Checking customer regions.",
                        tool_calls=[{"name": "get_customer_regions", "args": {"customer_id": "C12382"}, "id": "c2"}]
                    )
                else:
                    return AIMessage(
                        content="Investigation complete.",
                        tool_calls=[],
                        additional_kwargs={
                            "hypotheses": [
                                {
                                    "id": "h1",
                                    "title": "Legitimate Recurring Behavior",
                                    "description": "Routine spend in region 444",
                                    "confidence": 0.6,
                                    "supporting_evidence": ["Region 444 established"],
                                    "contradicting_evidence": []
                                },
                                {
                                    "id": "h2",
                                    "title": "Counterfeit Cloning",
                                    "description": "Historical cloning precedent",
                                    "confidence": 0.4,
                                    "supporting_evidence": [],
                                    "contradicting_evidence": []
                                }
                            ]
                        }
                    )

        llm = DynamicLLM()
        agent = InvestigationAgent(llm)

        state = create_initial_state("HHG-001", "C12382", "C12382-K1", "3514030")

        # Cycle 1
        res1 = agent.node(state)
        self.assertEqual(res1["iteration_count"], 1)
        last_msg = res1["messages"][-1]
        self.assertEqual(last_msg.tool_calls[0]["name"], "get_transaction")

        # Execute tool
        executor = ToolExecutor()
        exec_res = executor.execute(last_msg.tool_calls[0])
        state["messages"] = res1["messages"] + [exec_res["message"]]
        state["evidence"] = [exec_res["evidence"]]
        state["iteration_count"] = 1

        # Cycle 2
        res2 = agent.node(state)
        self.assertEqual(res2["iteration_count"], 2)
        last_msg2 = res2["messages"][-1]
        self.assertEqual(last_msg2.tool_calls[0]["name"], "get_customer_regions")

    # ----------------------------------------------------------------------
    # 9. MOCK MODE TESTS
    # ----------------------------------------------------------------------
    def test_mock_mode_full_pipeline(self):
        """Test that explicit mock mode executes the full pipeline offline."""
        os.environ["LLM_PROVIDER"] = "mock"
        inv_llm = get_investigator_llm(provider="mock")
        ass_llm = get_assessment_llm(provider="mock")

        graph = build_investigation_graph(inv_llm, assessment_llm=ass_llm)

        state = create_initial_state(
            case_id="HHG-001",
            customer_id="C12382",
            card_id="C12382-K1",
            flagged_txn_id="3514030",
            trigger_type="risk_score",
            risk_score=0.61,
        )

        final_state = graph.invoke(state)

        # Graph completes to END with assessment and policy decision
        self.assertEqual(final_state["case_id"], "HHG-001")
        self.assertIn("assessment", final_state)
        self.assertIn("policy_decision", final_state)
        self.assertGreater(len(final_state.get("tools_used", [])), 0)
        self.assertGreater(len(final_state.get("evidence", [])), 0)
        self.assertGreater(len(final_state.get("hypotheses", [])), 0)

        ass = final_state["assessment"]
        self.assertIn(ass["verdict"], ["confirmed_fraud", "suspected_fraud", "uncertain", "legitimate"])
        self.assertEqual(ass["affected_txn_ids"], ["3514030"])
        self.assertAlmostEqual(ass["exposure"], 77.07, places=2)


if __name__ == "__main__":
    unittest.main()
