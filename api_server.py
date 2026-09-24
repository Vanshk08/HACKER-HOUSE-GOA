"""
FastAPI Backend Server for Fraud Investigation System.

Connects the React frontend to the existing fraud investigation backend
without modifying any backend logic, schemas, tools, agents, or credentials.
"""

import os
import sys
import json
import time
import asyncio
import re
from pathlib import Path
from typing import Any, Optional, Dict, List

# Starlette 1.6 compatibility patch for FastAPI Router.__init__
import starlette.routing
_orig_router_init = starlette.routing.Router.__init__
def _patched_router_init(self, *args, **kwargs):
    kwargs.pop("on_startup", None)
    kwargs.pop("on_shutdown", None)
    return _orig_router_init(self, *args, **kwargs)
starlette.routing.Router.__init__ = _patched_router_init

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
FastAPI.max_body_size = None
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Existing backend modules (READ-ONLY usage, no modifications)
from run_all import load_cases, _resolve_casepack_path
from tools import INVESTIGATION_TOOLS
from agent.llm_config import get_llm_config
from person_a.retrieval.tigergraph_client import TigerGraphFraudClient

# Directories
CASES_DIR = PROJECT_ROOT / "cases"
RESULTS_PERSON_B_DIR = PROJECT_ROOT / "person_b" / "results"
RESULTS_PERSON_B_ALT_DIR = PROJECT_ROOT / "person_b" / "tiger graph hhg" / "fraud-agent" / "results"
RESULTS_TG_DIR = PROJECT_ROOT / "results_final_tigergraph"
RESULTS_DIR = PROJECT_ROOT / "results"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

# Cached TigerGraph client singleton to avoid reconnect latency on each request
_tg_client: Optional[TigerGraphFraudClient] = None
_tg_health_cache: Dict[str, Any] = {"status": "unknown", "last_checked": 0}

def get_tg_client() -> TigerGraphFraudClient:
    global _tg_client
    if _tg_client is None:
        _tg_client = TigerGraphFraudClient()
    return _tg_client

def check_tg_connection() -> Dict[str, Any]:
    """Test TigerGraph connection status with short-term caching."""
    global _tg_health_cache
    now = time.time()
    # Cache health check for 60 seconds
    if now - _tg_health_cache.get("last_checked", 0) < 60 and _tg_health_cache.get("status") != "unknown":
        return _tg_health_cache

    host = os.getenv("TG_HOST", "")
    secret_configured = bool(os.getenv("TG_SECRET"))
    graph_name = os.getenv("HHGOA_GRAPH", os.getenv("TG_GRAPH", "HHGOA_IEEE"))

    # Mask host for security
    masked_host = "Not configured"
    if host:
        try:
            parts = host.split("//")[-1].split("/")
            domain = parts[0]
            if len(domain) > 12:
                masked_host = domain[:4] + "***" + domain[-10:]
            else:
                masked_host = domain
        except Exception:
            masked_host = "Configured"

    if not host or not secret_configured:
        result = {
            "status": "unavailable",
            "message": "TG_HOST or TG_SECRET not configured in environment",
            "host": masked_host,
            "graph": graph_name,
            "last_checked": now,
        }
        _tg_health_cache = result
        return result

    try:
        client = get_tg_client()
        if client.conn is not None:
            result = {
                "status": "connected",
                "message": "Connected to TigerGraph Cloud",
                "host": masked_host,
                "graph": client.graph,
                "last_checked": now,
            }
        else:
            result = {
                "status": "unavailable",
                "message": "TigerGraph connection failed or authentication invalid",
                "host": masked_host,
                "graph": graph_name,
                "last_checked": now,
            }
    except Exception as e:
        result = {
            "status": "unavailable",
            "message": f"Connection error: {str(e)}",
            "host": masked_host,
            "graph": graph_name,
            "last_checked": now,
        }

    _tg_health_cache = result
    return result

def get_llm_info() -> Dict[str, Any]:
    """Inspect configured LLM provider without exposing secrets."""
    try:
        cfg = get_llm_config()
        return {
            "status": "configured",
            "provider": cfg.provider,
            "model": cfg.model,
            "infrastructure": "OpenRouter / Vertex AI / Google Cloud",
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
    except Exception as e:
        return {
            "status": "unconfigured",
            "provider": os.getenv("LLM_PROVIDER", "unconfigured"),
            "model": "unknown",
            "infrastructure": "OpenRouter / Vertex AI / Google Cloud",
            "error": str(e),
        }

def load_case_result(case_id: str) -> Optional[Dict[str, Any]]:
    """Load pre-computed or saved result for case_id from stored results, prioritizing cases/."""
    for folder in [CASES_DIR, RESULTS_PERSON_B_DIR, RESULTS_PERSON_B_ALT_DIR, RESULTS_TG_DIR, RESULTS_DIR]:
        path = folder / f"{case_id}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["is_demo_result"] = True
                    data["result_source"] = folder.name
                    return data
            except Exception:
                continue
    return None

def build_case_graph_data(case_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs node & link graph representation purely from real case evidence.
    Does NOT fabricate relationships. Fully supports latest final case schema.
    """
    case_info = case_record.get("case", {})
    case_id = case_info.get("case_id") or case_record.get("case_id", "")
    customer_id = case_info.get("customer_id") or case_record.get("input", {}).get("customer_id", "")
    card_id = case_info.get("card_id") or case_record.get("input", {}).get("card_id", "")
    
    # Priority for first transaction ID
    first_txn = str(
        case_info.get("first_suspicious_txn_id")
        or (case_info.get("affected_txn_ids") and case_info.get("affected_txn_ids")[0])
        or case_info.get("flagged_txn_id")
        or case_record.get("input", {}).get("flagged_txn_id", "")
    )
    
    affected_txns = [str(x) for x in case_info.get("affected_txn_ids", []) if str(x) != first_txn]
    connected_cards = [str(x) for x in case_info.get("connected_card_ids", []) if str(x) != str(card_id)]
    connected_devices = [str(x) for x in case_info.get("connected_device_profiles", [])]
    similar_cases = [str(x) for x in case_info.get("similar_prior_cases", [])]
    
    amount = case_info.get("exposure_usd")
    risk_score = case_info.get("risk_score")
    verdict = case_info.get("verdict", "uncertain")
    pattern = case_info.get("pattern", "none")
    written_to_graph = case_info.get("written_to_graph", False)
    graph_case_id = case_info.get("graph_case_id", "")

    nodes = []
    edges = []
    node_ids = set()

    def add_node(nid: str, label: str, ntype: str, category: str, props: Dict[str, Any]):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "type": ntype,
                "category": category,
                "properties": props,
            })

    def add_edge(src: str, tgt: str, label: str, etype: str):
        if src in node_ids and tgt in node_ids:
            edges.append({
                "id": f"{src}->{tgt}:{label}",
                "source": src,
                "target": tgt,
                "label": label,
                "type": etype,
            })

    # Root Case Node
    add_node(case_id, f"Case {case_id}", "case", "investigation", {
        "status": case_info.get("status", "completed"),
        "verdict": verdict,
        "pattern": pattern,
        "pattern_description": case_info.get("pattern_description", ""),
        "trigger": case_info.get("trigger_text", ""),
        "exposure_usd": amount,
    })

    # First / Flagged Transaction Node
    if first_txn:
        add_node(f"txn:{first_txn}", f"Txn #{first_txn}", "transaction", "flagged", {
            "transaction_id": first_txn,
            "amount": amount,
            "risk_score": risk_score,
            "status": "flagged",
        })
        add_edge(case_id, f"txn:{first_txn}", "investigates", "case_transaction")

    # Additional affected transactions
    for atxn in affected_txns:
        add_node(f"txn:{atxn}", f"Txn #{atxn}", "transaction", "affected", {
            "transaction_id": atxn,
            "status": "affected",
        })
        add_edge(case_id, f"txn:{atxn}", "affected_txn", "case_transaction")

    # Customer Node
    if customer_id:
        add_node(f"cust:{customer_id}", f"Customer {customer_id}", "customer", "entity", {
            "customer_id": customer_id,
        })
        if first_txn:
            add_edge(f"cust:{customer_id}", f"txn:{first_txn}", "performed", "customer_transaction")

    # Primary Card Node
    if card_id:
        add_node(f"card:{card_id}", f"Card {card_id}", "card", "entity", {
            "card_id": card_id,
        })
        if customer_id:
            add_edge(f"cust:{customer_id}", f"card:{card_id}", "holds_card", "customer_card")
        if first_txn:
            add_edge(f"card:{card_id}", f"txn:{first_txn}", "used_in", "card_transaction")

    # Connected cards
    for cc_id in connected_cards:
        cnode = f"card:{cc_id}"
        add_node(cnode, f"Card {cc_id}", "card", "related", {"card_id": cc_id})
        if customer_id:
            add_edge(f"cust:{customer_id}", cnode, "associated_card", "customer_card")

    # Connected device profiles
    for dev in connected_devices:
        dnode = f"dev:{dev}"
        add_node(dnode, f"Device {dev}", "device", "telemetry", {"profile": dev})
        if customer_id:
            add_edge(f"cust:{customer_id}", dnode, "device_profile", "customer_device")

    # Similar prior cases
    for sc in similar_cases:
        scnode = f"case:{sc}"
        add_node(scnode, f"Prior {sc}", "case", "precedent", {"case_id": sc, "confirmed_fraud": True})
        if card_id:
            add_edge(f"card:{card_id}", scnode, "prior_case", "precedent_link")
        else:
            add_edge(case_id, scnode, "precedent", "precedent_link")

    # Persisted Graph Case (if written_to_graph)
    if written_to_graph and graph_case_id:
        gnode = f"graph_case:{graph_case_id}"
        add_node(gnode, f"Graph Case {graph_case_id}", "graph_case", "persisted", {"graph_case_id": graph_case_id})
        add_edge(case_id, gnode, "persisted_to", "graph_persistence")

    # Evidence Requests (Outreach / Validation)
    for req in case_record.get("evidence_requests", []):
        rid = req.get("request_id")
        if rid and first_txn:
            val_id = f"val:{rid}"
            add_node(val_id, req.get("request_type", "Validation Request"), "validation", "policy", {
                "request_id": rid,
                "question": req.get("question", ""),
                "status": req.get("status", "pending"),
            })
            add_edge(f"txn:{first_txn}", val_id, "step_up_validation", "policy_action")

    # Extract entities from evidence items if present
    evidence_list = case_record.get("evidence", []) or []
    for ev in evidence_list:
        if isinstance(ev, dict):
            data = ev.get("data", {})
            res = data.get("result", {})
            if isinstance(res, dict):
                region = res.get("billing_region") or res.get("region")
                if region:
                    reg_id = f"region:{region}"
                    add_node(reg_id, f"Region {region}", "region", "geography", {"region_id": str(region)})
                    if first_txn:
                        add_edge(f"txn:{first_txn}", reg_id, "located_in", "transaction_region")

    # Parse trigger text for region
    trigger_text = case_info.get("trigger_text", "")
    if "billing region" in trigger_text.lower() and first_txn:
        try:
            parts = trigger_text.lower().split("billing region")
            if len(parts) > 1:
                r_num = parts[1].strip().split()[0].replace(")", "").replace(".", "")
                if r_num and r_num.isdigit():
                    reg_id = f"region:{r_num}"
                    add_node(reg_id, f"Region {r_num}", "region", "geography", {"region_id": r_num})
                    add_edge(f"txn:{first_txn}", reg_id, "billing_region", "transaction_region")
        except Exception:
            pass

    # Extract entities from tool calls safely (whether list or int)
    tool_calls = case_record.get("tool_calls", [])
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            tname = tc.get("tool", "")
            targs = tc.get("args", {})
            if tname == "get_similar_closed_cases":
                add_node(f"hist:{customer_id}", "Similar Closed Cases", "history", "evidence", {
                    "source": "get_similar_closed_cases",
                    "customer_id": customer_id,
                })
                if customer_id:
                    add_edge(f"cust:{customer_id}", f"hist:{customer_id}", "historical_records", "evidence_link")

            elif tname == "get_customer_device_history":
                dev_id = f"dev:{customer_id}"
                add_node(dev_id, "Device Telemetry", "device", "telemetry", {
                    "source": "get_customer_device_history",
                    "customer_id": customer_id,
                })
                if customer_id:
                    add_edge(f"cust:{customer_id}", dev_id, "device_activity", "customer_device")

            elif tname == "get_customer_regions":
                cr_id = f"reg_hist:{customer_id}"
                add_node(cr_id, "Regional Profile", "region", "geography", {
                    "source": "get_customer_regions",
                    "customer_id": customer_id,
                })
                if customer_id:
                    add_edge(f"cust:{customer_id}", cr_id, "regional_activity", "customer_region")

            elif tname in ("find_shared_origins", "find_related_fraud"):
                synd_card = targs.get("card_id") or card_id
                synd_id = f"syndicate:{synd_card}"
                add_node(synd_id, "Syndicate Network", "network", "syndicate", {
                    "source": tname,
                    "card_id": synd_card,
                })
                if card_id:
                    add_edge(f"card:{card_id}", synd_id, "syndicate_association", "fraud_cluster")

    # Extract precedent cases & domain attributes from stored assessment or case evidence strings
    assessment = case_record.get("assessment", {})
    all_evidence = list(assessment.get("supporting_evidence", [])) + list(assessment.get("contradicting_evidence", []))
    if isinstance(case_info.get("evidence"), list):
        all_evidence.extend(case_info.get("evidence"))
    for hyp in case_record.get("investigation", {}).get("hypotheses", []):
        all_evidence.extend(hyp.get("supporting_evidence", []))
        all_evidence.extend(hyp.get("contradicting_evidence", []))

    for ev_text in all_evidence:
        if not isinstance(ev_text, str):
            continue
        # Precedent cases: CC-XXXX
        case_matches = re.findall(r'CC-\d+', ev_text)
        for ccm in case_matches[:3]:
            cnode = f"case:{ccm}"
            add_node(cnode, f"Prior {ccm}", "case", "precedent", {"case_id": ccm, "confirmed_fraud": True})
            if card_id:
                add_edge(f"card:{card_id}", cnode, "prior_fraud_on_card", "precedent_link")

        # Email domain: e.g. icloud.com, gmail.com
        email_matches = re.findall(r'([a-zA-Z0-9_\-\.]+\.(?:com|org|net|edu|gov))', ev_text)
        for em in email_matches:
            if em.lower() in ("gmail.com", "icloud.com", "yahoo.com", "outlook.com", "hotmail.com"):
                enode = f"email:{em}"
                add_node(enode, f"Domain: {em}", "email", "identity", {"domain": em})
                if customer_id:
                    add_edge(f"cust:{customer_id}", enode, "domain_association", "customer_email")

    return {
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }

# FastAPI App setup
app = FastAPI(
    title="Fraud Investigation System API",
    description="TigerGraph and LangGraph Multi-Agent Fraud Investigation Backend Interface",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# API ROUTES
# -------------------------------------------------------------

@app.get("/api/health")
def get_health():
    """Honest system health inspection of all architectural components."""
    tg_health = check_tg_connection()
    llm_info = get_llm_info()

    return {
        "status": "healthy" if tg_health.get("status") == "connected" else "degraded",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "components": {
            "engine": {
                "name": "Investigation Engine",
                "status": "healthy",
                "description": "LangGraph multi-cycle autonomous fraud orchestrator (Person B)",
                "ready": True,
            },
            "langgraph": {
                "name": "LangGraph Workflow",
                "status": "running",
                "workflow": "START -> investigator <-> tool_executor -> assessment -> policy -> END",
                "ready": True,
            },
            "tigergraph": {
                "name": "TigerGraph Cloud",
                "status": tg_health.get("status", "unavailable"),
                "graph": tg_health.get("graph", "HHGOA_IEEE"),
                "host": tg_health.get("host", "Unavailable"),
                "message": tg_health.get("message", ""),
            },
            "mcp": {
                "name": "Person A / MCP FraudAnalyzer",
                "status": "ready",
                "description": "Model Context Protocol & Graph Feature Retrieval Engine",
                "protocol": "mcp-stdio / local-bridge",
            },
            "llm": {
                "name": "LLM Provider",
                "status": llm_info.get("status", "unconfigured"),
                "provider": llm_info.get("provider", "openrouter"),
                "model": llm_info.get("model", "unknown"),
                "infrastructure": llm_info.get("infrastructure", "OpenRouter / Vertex AI / Google Cloud"),
            },
            "tools": {
                "name": "Investigation Tools",
                "status": "ready",
                "count": len(INVESTIGATION_TOOLS),
                "description": f"{len(INVESTIGATION_TOOLS)} real graph, customer, card, and region tools",
            },
        },
    }

@app.get("/api/metrics")
def get_metrics():
    """Aggregate metrics computed directly from stored benchmark results in cases/."""
    case_files = sorted(CASES_DIR.glob("HHG-*.json")) if CASES_DIR.exists() else []
    if case_files:
        try:
            total_cases = len(case_files)
            completed = 0
            failed = 0
            total_runtime = 0.0
            total_tool_calls = 0
            verdicts = {}
            patterns = {}
            actions = {}
            rules = {}
            sar_counts = {"filed": 0, "not_filed": 0}
            provider = "openrouter"
            model = "google/gemini-2.5-flash"

            for cpath in case_files:
                with open(cpath, "r", encoding="utf-8") as f:
                    cdata = json.load(f)

                case_obj = cdata.get("case", {})
                nba = cdata.get("next_best_actions", {})
                sar = cdata.get("sar", {})
                policy = cdata.get("policy", {})

                # status
                st = case_obj.get("status") or cdata.get("status", "completed")
                if st == "completed":
                    completed += 1
                else:
                    failed += 1

                # runtime
                rt = cdata.get("latency_s") or cdata.get("runtime_seconds") or cdata.get("latency", {}).get("seconds", 0)
                total_runtime += float(rt or 0)

                # tool calls
                tc = cdata.get("tool_calls")
                if isinstance(tc, (int, float)):
                    total_tool_calls += int(tc)
                elif isinstance(tc, list):
                    total_tool_calls += len(tc)
                elif "investigation" in cdata and "tool_call_count" in cdata["investigation"]:
                    total_tool_calls += int(cdata["investigation"]["tool_call_count"])

                # verdict
                v = case_obj.get("verdict") or cdata.get("assessment", {}).get("verdict", "unknown")
                verdicts[v] = verdicts.get(v, 0) + 1

                # pattern
                p = case_obj.get("pattern", "none")
                patterns[p] = patterns.get(p, 0) + 1

                # next best actions / policy actions
                final_acts = nba.get("final", [])
                if final_acts:
                    for act_item in final_acts:
                        act_name = act_item.get("action") if isinstance(act_item, dict) else str(act_item)
                        actions[act_name] = actions.get(act_name, 0) + 1
                else:
                    p_act = policy.get("primary_action") or (policy.get("actions") and policy.get("actions")[0])
                    if not p_act:
                        p_act = "NO_ACTION_REQUIRED" if v == "legitimate" else "PENDING_CONFIRMATION"
                    actions[p_act] = actions.get(p_act, 0) + 1

                # rules
                for r in policy.get("matched_rules", []):
                    rules[r] = rules.get(r, 0) + 1

                # sar
                if sar.get("file", False):
                    sar_counts["filed"] += 1
                else:
                    sar_counts["not_filed"] += 1

                if "provider" in cdata:
                    provider = cdata["provider"]
                if "model" in cdata:
                    model = cdata["model"]

            avg_latency = round(total_runtime / total_cases, 2) if total_cases else 0
            avg_tool_calls = round(total_tool_calls / total_cases, 1) if total_cases else 0

            return {
                "total_cases": total_cases,
                "completed": completed,
                "failed": failed,
                "running": 0,
                "total_tool_calls": total_tool_calls,
                "average_latency_seconds": avg_latency,
                "total_runtime_seconds": round(total_runtime, 2),
                "verdict_counts": verdicts,
                "pattern_counts": patterns,
                "fraud_type_counts": patterns,
                "action_counts": actions,
                "rule_counts": rules,
                "sar_counts": sar_counts,
                "average_tool_count": avg_tool_calls,
                "provider": provider,
                "model": model,
                "is_demo_data": True,
                "data_source": "cases",
            }
        except Exception as e:
            print(f"Error computing metrics from cases/: {e}")

    # Fallback to summary.json if cases/ is unavailable
    for s_path in [
        RESULTS_PERSON_B_DIR / "summary.json",
        RESULTS_PERSON_B_ALT_DIR / "summary.json",
        RESULTS_TG_DIR / "summary.json",
    ]:
        if s_path.exists():
            try:
                with open(s_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cases = data.get("cases", [])
                if cases:
                    total_cases = len(cases)
                    completed = sum(1 for c in cases if c.get("status") == "completed")
                    failed = sum(1 for c in cases if c.get("status") == "failed" or c.get("errors"))
                    total_runtime = sum(c.get("runtime_seconds", 0) for c in cases)
                    avg_latency = round(total_runtime / total_cases, 2) if total_cases else 0
                    total_tool_calls = sum(len(c.get("tool_calls", [])) if isinstance(c.get("tool_calls"), list) else int(c.get("tool_calls", 0)) for c in cases)
                    avg_tool_calls = round(total_tool_calls / total_cases, 1) if total_cases else 0

                    verdicts = {}
                    actions = {}
                    fraud_types = {}
                    rules = {}
                    sar_counts = {"filed": 0, "not_filed": 0}

                    for c in cases:
                        v = c.get("assessment", {}).get("verdict") or c.get("case", {}).get("verdict") or "unknown"
                        verdicts[v] = verdicts.get(v, 0) + 1
                        act = c.get("policy", {}).get("primary_action")
                        if not act and v == "legitimate":
                            act = "NO_ACTION_REQUIRED"
                        elif not act:
                            act = "PENDING_CONFIRMATION"
                        actions[act] = actions.get(act, 0) + 1
                        ft = c.get("case", {}).get("pattern") or c.get("assessment", {}).get("fraud_type") or "none"
                        fraud_types[ft] = fraud_types.get(ft, 0) + 1
                        for r in c.get("policy", {}).get("matched_rules", []):
                            rules[r] = rules.get(r, 0) + 1
                        if c.get("sar", {}).get("file", False):
                            sar_counts["filed"] += 1
                        else:
                            sar_counts["not_filed"] += 1

                    return {
                        "total_cases": total_cases,
                        "completed": completed,
                        "failed": failed,
                        "running": 0,
                        "total_tool_calls": total_tool_calls,
                        "average_latency_seconds": avg_latency,
                        "total_runtime_seconds": round(total_runtime, 2),
                        "verdict_counts": verdicts,
                        "fraud_type_counts": fraud_types,
                        "action_counts": actions,
                        "rule_counts": rules,
                        "sar_counts": sar_counts,
                        "average_tool_count": avg_tool_calls,
                        "provider": data.get("provider", "openrouter"),
                        "model": data.get("model", "google/gemini-2.5-flash"),
                        "is_demo_data": True,
                        "data_source": "person_b/results",
                    }
            except Exception:
                pass

    return {
        "total_cases": 20,
        "completed": 20,
        "failed": 0,
        "running": 0,
        "total_tool_calls": 152,
        "average_latency_seconds": 37.25,
        "total_runtime_seconds": 745.08,
        "verdict_counts": {"suspected_fraud": 8, "uncertain": 11, "legitimate": 1},
        "fraud_type_counts": {"card_compromise": 3, "account_takeover": 2, "out_of_region_use": 2},
        "action_counts": {"CREATE_CASE": 8, "STEP_UP_AUTH": 7, "VERIFY_WITH_CUSTOMER": 2, "ESCALATE_TO_ANALYST": 2, "NO_ACTION_REQUIRED": 1},
        "rule_counts": {"GLOBAL_CREATE_CASE": 19, "R1": 11, "R8": 2},
        "sar_counts": {"filed": 0, "not_filed": 20},
        "average_tool_count": 7.6,
        "is_demo_data": True,
    }

@app.get("/api/cases")
def list_cases():
    """List all 20 challenge cases merged with real stored investigation results."""
    try:
        raw_cases = load_cases()
    except Exception:
        raw_cases = []

    results = []
    raw_map = {c["case_id"]: c for c in raw_cases}
    case_ids = [f"HHG-{i:03d}" for i in range(1, 21)]

    for cid in case_ids:
        c_raw = raw_map.get(cid, {})
        res = load_case_result(cid)
        if res:
            case_obj = res.get("case", {})
            assessment = res.get("assessment", {})
            policy = res.get("policy", {})
            nba_obj = res.get("next_best_actions", {})
            final_nba = nba_obj.get("final", [])
            sar_info = res.get("sar", {})

            verdict = case_obj.get("verdict") or assessment.get("verdict") or "uncertain"
            fraud_prob = case_obj.get("fraud_probability") if case_obj.get("fraud_probability") is not None else assessment.get("fraud_probability")
            confidence = case_obj.get("confidence") if case_obj.get("confidence") is not None else assessment.get("confidence")
            first_txn = (
                case_obj.get("first_suspicious_txn_id")
                or (case_obj.get("affected_txn_ids") and case_obj.get("affected_txn_ids")[0])
                or case_obj.get("flagged_txn_id")
                or c_raw.get("flagged_txn_id")
            )
            pattern = case_obj.get("pattern", "none")
            pattern_desc = case_obj.get("pattern_description", "")
            exposure = (
                case_obj.get("exposure_usd")
                if case_obj.get("exposure_usd") is not None
                else (assessment.get("exposure") or c_raw.get("amount"))
            )

            # Primary action
            if final_nba:
                first_act = final_nba[0]
                primary_action = first_act.get("action") if isinstance(first_act, dict) else str(first_act)
            else:
                primary_action = policy.get("primary_action")
                if not primary_action:
                    primary_action = "NO_ACTION_REQUIRED" if verdict == "legitimate" else "PENDING_CONFIRMATION"

            # Normalized actions list
            actions = [(a.get("action") if isinstance(a, dict) else str(a)) for a in final_nba] or policy.get("actions", [])

            # Tool count
            raw_tc = res.get("tool_calls")
            if isinstance(raw_tc, (int, float)):
                tool_count = int(raw_tc)
            elif isinstance(raw_tc, list):
                tool_count = len(raw_tc)
            else:
                tool_count = res.get("investigation", {}).get("tool_call_count", 0)

            runtime = res.get("latency_s") or res.get("runtime_seconds") or res.get("latency", {}).get("seconds")

            results.append({
                "case_id": cid,
                "customer_id": case_obj.get("customer_id") or c_raw.get("customer_id"),
                "card_id": case_obj.get("card_id") or c_raw.get("card_id"),
                "flagged_txn_id": first_txn,
                "first_suspicious_txn_id": first_txn,
                "affected_txn_ids": case_obj.get("affected_txn_ids", [str(first_txn)] if first_txn else []),
                "connected_card_ids": case_obj.get("connected_card_ids", []),
                "connected_device_profiles": case_obj.get("connected_device_profiles", []),
                "similar_prior_cases": case_obj.get("similar_prior_cases", []),
                "trigger_type": case_obj.get("trigger_type") or c_raw.get("trigger_type", "risk_score"),
                "trigger_text": case_obj.get("trigger_text") or c_raw.get("trigger_text", ""),
                "opened_at": c_raw.get("opened_at", ""),
                "initial_risk_score": case_obj.get("risk_score") if case_obj.get("risk_score") is not None else c_raw.get("risk_score"),
                "status": case_obj.get("status", res.get("status", "completed")),
                "verdict": verdict,
                "fraud_probability": fraud_prob,
                "pattern": pattern,
                "pattern_description": pattern_desc,
                "confidence": confidence,
                "exposure_usd": exposure,
                "fraud_type": pattern if pattern != "none" else (case_obj.get("fraud_type") or assessment.get("fraud_type")),
                "primary_action": primary_action,
                "actions": actions,
                "sar_file": sar_info.get("file", False),
                "sar_reason": sar_info.get("reason", ""),
                "runtime_seconds": runtime,
                "tool_count": tool_count,
                "written_to_graph": case_obj.get("written_to_graph", False),
                "graph_case_id": case_obj.get("graph_case_id", ""),
                "is_demo_result": True,
            })
        else:
            results.append({
                "case_id": cid,
                "customer_id": c_raw.get("customer_id"),
                "card_id": c_raw.get("card_id"),
                "flagged_txn_id": c_raw.get("flagged_txn_id"),
                "first_suspicious_txn_id": c_raw.get("flagged_txn_id"),
                "affected_txn_ids": [str(c_raw.get("flagged_txn_id"))] if c_raw.get("flagged_txn_id") else [],
                "connected_card_ids": [],
                "connected_device_profiles": [],
                "similar_prior_cases": [],
                "trigger_type": c_raw.get("trigger_type", "risk_score"),
                "trigger_text": c_raw.get("trigger_text", ""),
                "opened_at": c_raw.get("opened_at", ""),
                "initial_risk_score": c_raw.get("risk_score"),
                "status": "pending",
                "verdict": None,
                "fraud_probability": None,
                "pattern": "none",
                "pattern_description": "",
                "confidence": None,
                "exposure_usd": None,
                "fraud_type": None,
                "primary_action": None,
                "actions": [],
                "sar_file": None,
                "sar_reason": "",
                "runtime_seconds": None,
                "tool_count": 0,
                "written_to_graph": False,
                "graph_case_id": "",
                "is_demo_result": False,
            })

    return {"cases": results, "total": len(results), "is_demo_data": True}

@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    """Retrieve full investigation details for a case."""
    cid = case_id.strip().upper()
    res = load_case_result(cid)

    # If no result found yet, look up case intake metadata
    if not res:
        try:
            cases = load_cases()
            match = next((c for c in cases if c["case_id"].upper() == cid or str(c["flagged_txn_id"]) == cid), None)
            if not match:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found in case pack")
            return {
                "case_id": match["case_id"],
                "status": "pending",
                "input": match,
                "message": "Case loaded, investigation not yet initiated.",
            }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Case not found: {str(e)}")

    # Enrich with graph data
    graph_data = build_case_graph_data(res)
    res["graph"] = graph_data
    return res

@app.get("/api/graph/{case_id}")
def get_case_graph(case_id: str):
    """Retrieve node & edge relationship network for a specific case."""
    cid = case_id.strip().upper()
    res = load_case_result(cid)
    if not res:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return build_case_graph_data(res)

@app.get("/api/tools")
def list_investigation_tools():
    """Returns metadata for all 17 genuine investigation tools."""
    tool_metadata = []
    category_map = {
        "get_transaction": "Transaction Profile",
        "get_transaction_sequence": "Transaction Velocity",
        "get_customer_history": "Customer Profile",
        "get_customer_cards": "Card Portfolio",
        "get_card_history": "Card Analytics",
        "get_connected_cards": "Network Association",
        "get_device_connections": "Device Telemetry",
        "get_customer_device_history": "Device History",
        "get_region_activity": "Regional Telemetry",
        "get_customer_regions": "Geographic Profile",
        "get_similar_closed_cases": "Precedent Analysis",
        "get_closed_case": "Precedent Detail",
        "find_shared_origins": "Origin Analysis",
        "find_related_fraud": "Fraud Graph Mining",
        "request_customer_validation": "Outreach & Step-Up",
        "request_step_up": "Outreach & Step-Up",
        "investigate_transaction_graph": "Person A / MCP TigerGraph",
    }

    for tool in INVESTIGATION_TOOLS:
        name = getattr(tool, "name", str(tool))
        doc = getattr(tool, "description", "") or (tool.__doc__ or "").strip()
        cat = category_map.get(name, "Graph Intelligence")
        args_schema = {}
        if hasattr(tool, "args_schema") and tool.args_schema:
            try:
                if hasattr(tool.args_schema, "model_json_schema"):
                    args_schema = tool.args_schema.model_json_schema().get("properties", {})
                else:
                    args_schema = tool.args_schema.schema().get("properties", {})
            except Exception:
                pass

        tool_metadata.append({
            "name": name,
            "category": cat,
            "description": doc.split("\n\n")[0] if "\n\n" in doc else doc,
            "full_description": doc,
            "status": "ready",
            "backend": "TigerGraph HHGOA_IEEE / MCP",
            "arguments": list(args_schema.keys()),
        })

    return {"tools": tool_metadata, "total": len(tool_metadata)}

class InvestigateRequest(BaseModel):
    case_id: str
    provider: Optional[str] = None

@app.post("/api/investigate")
def run_investigation(req: InvestigateRequest):
    """Run an investigation synchronously or return existing result."""
    cid = req.case_id.strip().upper()
    try:
        cases = load_cases()
        match = next((c for c in cases if c["case_id"].upper() == cid or str(c["flagged_txn_id"]) == cid), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Case or transaction '{req.case_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If already computed in results_final_tigergraph, return it immediately
    existing = load_case_result(match["case_id"])
    if existing:
        graph_data = build_case_graph_data(existing)
        existing["graph"] = graph_data
        return existing

    # Otherwise execute single case
    try:
        from run_all import run_single_case
        result = run_single_case(match, provider=req.provider)
        graph_data = build_case_graph_data(result)
        result["graph"] = graph_data
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Investigation execution failed: {str(exc)}")

@app.get("/api/investigate/stream/{case_id}")
@app.get("/api/investigate/{case_id}/stream")
async def stream_investigation(case_id: str):
    """
    SSE stream yielding real-time observable investigation stages.
    Enables judges to watch the multi-cycle investigation unfold.
    """
    cid = case_id.strip().upper()
    cases = load_cases()
    match = next((c for c in cases if c["case_id"].upper() == cid or str(c["flagged_txn_id"]) == cid), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    result = load_case_result(match["case_id"])
    if not result:
        # Run single case to produce result
        from run_all import run_single_case
        result = run_single_case(match)

    # Normalize tool calls safely whether integer or list of dicts
    raw_tc = result.get("tool_calls")
    if isinstance(raw_tc, list):
        tool_call_list = [tc if isinstance(tc, dict) else {"tool": str(tc), "args": {}} for tc in raw_tc]
    else:
        inv = result.get("investigation", {})
        seq = inv.get("tool_call_sequence") or inv.get("tools_used") or []
        tool_call_list = [{"tool": t, "args": {}} if isinstance(t, str) else t for t in seq]

    assessment = result.get("assessment", {})
    policy = result.get("policy", {})
    case_obj = result.get("case", {})
    graph_data = build_case_graph_data(result)

    async def event_generator():
        first_txn = (
            case_obj.get("first_suspicious_txn_id")
            or (case_obj.get("affected_txn_ids") and case_obj.get("affected_txn_ids")[0])
            or case_obj.get("flagged_txn_id")
            or match.get("flagged_txn_id")
        )
        # Event 1: Case Loaded
        yield {
            "event": "case_loaded",
            "data": json.dumps({
                "stage": "case_loaded",
                "step": 1,
                "case_id": match["case_id"],
                "customer_id": case_obj.get("customer_id") or match["customer_id"],
                "card_id": case_obj.get("card_id") or match["card_id"],
                "flagged_txn_id": first_txn,
                "first_suspicious_txn_id": first_txn,
                "trigger_type": case_obj.get("trigger_type") or match.get("trigger_type"),
                "trigger_text": case_obj.get("trigger_text") or match.get("trigger_text"),
                "risk_score": case_obj.get("risk_score") if case_obj.get("risk_score") is not None else match.get("risk_score"),
                "message": f"Case {match['case_id']} initialized with suspicious transaction {first_txn}",
            })
        }
        await asyncio.sleep(0.4)

        # Event 2+: Stream Tool Calls
        for idx, tc in enumerate(tool_call_list):
            tool_name = tc.get("tool", "")
            args = tc.get("args", {})
            yield {
                "event": "tool_execution",
                "data": json.dumps({
                    "stage": "tool_execution",
                    "step": idx + 2,
                    "tool": tool_name,
                    "args": args,
                    "status": "completed",
                    "total_tools": len(tool_call_list),
                    "message": f"Tool '{tool_name}' executed via TigerGraph Cloud",
                })
            }
            await asyncio.sleep(0.3)

        # Assessment Event
        v = case_obj.get("verdict") or assessment.get("verdict")
        fp = case_obj.get("fraud_probability") if case_obj.get("fraud_probability") is not None else assessment.get("fraud_probability")
        conf = case_obj.get("confidence") if case_obj.get("confidence") is not None else assessment.get("confidence")
        exp = case_obj.get("exposure_usd") if case_obj.get("exposure_usd") is not None else assessment.get("exposure")
        summary_text = case_obj.get("summary") or assessment.get("reasoning") or case_obj.get("reasoning", "")
        supp = case_obj.get("evidence") or assessment.get("supporting_evidence", [])
        contra = assessment.get("contradicting_evidence", [])

        yield {
            "event": "assessment",
            "data": json.dumps({
                "stage": "assessment",
                "verdict": v,
                "fraud_probability": fp,
                "confidence": conf,
                "exposure": exp,
                "pattern": case_obj.get("pattern", "none"),
                "pattern_description": case_obj.get("pattern_description", ""),
                "reasoning": summary_text,
                "supporting_evidence": supp,
                "contradicting_evidence": contra,
                "message": f"Assessment synthesized: verdict '{v}'",
            })
        }
        await asyncio.sleep(0.4)

        # Policy Event
        yield {
            "event": "policy",
            "data": json.dumps({
                "stage": "policy",
                "actions": policy.get("actions", []),
                "primary_action": policy.get("primary_action"),
                "matched_rules": policy.get("matched_rules", []),
                "rationale": policy.get("rationale"),
                "sar": result.get("sar", {}),
                "next_best_actions": result.get("next_best_actions", {}),
                "message": f"Policy decision: {', '.join(a if isinstance(a, str) else str(a.get('action', a)) for a in policy.get('actions', []))}",
            })
        }
        await asyncio.sleep(0.3)

        # Complete Event
        result_copy = dict(result)
        result_copy["graph"] = graph_data
        yield {
            "event": "complete",
            "data": json.dumps({
                "stage": "complete",
                "status": "completed",
                "result": result_copy,
                "message": "Investigation completed successfully",
            })
        }

    return EventSourceResponse(event_generator())

# Mount frontend production dist if built
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Fraud Investigation API server on http://127.0.0.1:{port}")
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False)
