

````markdown
# TigerGraph Fraud Investigation Agent

## AI-Powered Fraud Investigation & Next-Best-Action System

An agentic fraud investigation system built for the **Hacker House Goa 2026 × TigerGraph** challenge.

The system investigates suspicious financial activity using **TigerGraph relationship data, transaction history, customer/card relationships, device and regional signals, historical closed cases, and an LLM-powered investigation workflow**.

Instead of treating a bank risk score as a final fraud decision, the system investigates the surrounding evidence, evaluates competing explanations, determines whether the available evidence is sufficient, applies deterministic fraud policy rules, and produces an auditable structured case.

---

## Demo

The frontend provides an analyst-style investigation dashboard showing:

- 20 challenge cases
- Fraud probability
- Investigation verdict
- Fraud pattern classification
- Evidence gathered
- Customer outreach
- Next-best actions
- SAR determination
- TigerGraph relationship visualization
- Connected customers, cards, transactions and domains
- Case history
- Structured investigation results

The application also supports a demo mode that displays the precomputed investigation results stored in the `cases/` directory.

---

# Problem

Fraud detection systems often identify transactions that deserve investigation, but a risk score alone does not explain:

- Why the transaction is suspicious
- Whether the activity is actually fraudulent
- What other entities are connected to the transaction
- Whether the same card, customer, device or region appears elsewhere
- Whether similar historical cases exist
- Whether more evidence is required
- What action should be taken
- Whether the case should be escalated
- Whether regulatory reporting is appropriate

Fraud investigation is therefore not simply a classification problem.

It is a reasoning and evidence-gathering problem.

This project implements an agentic investigation workflow that attempts to answer:

> **What happened, how far does the suspicious activity extend, what evidence supports or contradicts the hypothesis, and what should happen next?**

---

# Challenge

The Hacker House Goa challenge provides a fraud investigation dataset based on the IEEE-CIS Fraud Detection dataset.

The challenge removes the original fraud label and instead provides:

- Transaction data
- Bank risk scores
- Customers
- Cards
- Device information
- Email domains
- Billing regions
- Historical closed investigations
- Fraud policy
- Fraud patterns
- 20 benchmark investigation cases

The agent must investigate the provided cases without recovering the original public fraud labels.

The final system produces one structured answer file for each benchmark case.

---

# Key Idea

The system follows this general investigation loop:

```text
Initial Trigger
      |
      v
Investigation
      |
      v
TigerGraph / Evidence Tools
      |
      v
Evidence Collection
      |
      v
Competing Hypotheses
      |
      v
Assessment
      |
      v
Policy Engine
      |
      v
Next Best Action
      |
      +--------------------+
      |                    |
      | More evidence      | Enough evidence
      v                    v
Customer / Analyst       Final Case
Verification
      |
      v
Updated Assessment
````

The central design principle is:

> **A risk score is a reason to investigate, not a verdict.**

---

# Architecture

## High-Level Architecture

```text
                         +----------------------+
                         |   Challenge Case     |
                         |    HHG-001..020      |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |     LangGraph        |
                         |    Orchestrator      |
                         +----------+-----------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
          +-------------------+            +-------------------+
          |   Investigator    |            |   Tool Executor   |
          |       Node        |<---------->|                   |
          +---------+---------+            +---------+---------+
                    |                                |
                    |                                v
                    |                     +-------------------+
                    |                     |    TigerGraph    |
                    |                     | Graph / Queries   |
                    |                     +---------+---------+
                    |                               |
                    |                               v
                    |                     Customers / Cards
                    |                     Transactions
                    |                     Devices
                    |                     Regions
                    |                     Historical Cases
                    |
                    v
          +-------------------+
          |    Assessment     |
          |       Node        |
          +---------+---------+
                    |
                    v
          +-------------------+
          | Deterministic      |
          | Policy Engine      |
          |      R1 - R10      |
          +---------+---------+
                    |
                    v
          +-------------------+
          | Structured Case   |
          |     Output        |
          +---------+---------+
                    |
                    v
             cases/HHG-XXX.json
```

---

# Agent Framework

## LangGraph

The agent orchestration layer is implemented using **LangGraph**.

The investigation is represented as a stateful graph where each node operates on a shared investigation state.

The primary flow is:

```text
START
  |
  v
investigator
  |
  v
tool_executor
  |
  v
assessment
  |
  v
policy
  |
  v
END
```

The investigator can iterate through evidence gathering before the assessment stage.

This allows the system to maintain investigation state instead of treating each LLM call as an isolated request.

---

# Investigation Nodes

## 1. Investigator

The investigator determines what evidence should be gathered.

It can:

* Examine the initial trigger
* Generate investigation hypotheses
* Select investigation tools
* Investigate customers
* Investigate cards
* Investigate transactions
* Examine connected entities
* Search historical cases
* Investigate devices
* Investigate regions
* Request additional evidence
* Continue investigating when uncertainty remains

The investigator is designed to avoid assuming that every suspicious transaction is fraudulent.

---

## 2. Tool Executor

The tool executor executes the investigation tools selected by the agent.

The tool layer provides access to information such as:

* Transaction history
* Customer history
* Customer cards
* Card activity
* Device relationships
* Regional relationships
* Historical cases
* Graph relationships
* Evidence requests

Tool results are converted into structured evidence that can be consumed by the assessment stage.

---

## 3. Assessment

The assessment node synthesizes the collected evidence.

The assessment produces structured fields including:

```text
verdict
fraud_probability
fraud_type
exposure
affected_txn_ids
supporting_evidence
contradicting_evidence
reasoning
confidence
```

The assessment stage also validates transaction identifiers and ensures that calculated exposure is based on verified transactions rather than arbitrary LLM-generated values.

---

## 4. Policy Engine

The policy engine is deterministic.

The LLM does not directly decide whether high-impact actions such as blocking cards or filing reports should happen.

Instead:

```text
LLM Assessment
      |
      v
Deterministic Policy
      |
      v
Allowed Actions + Approval Route
```

This separation provides a stronger control boundary between probabilistic reasoning and operational decisions.

---

# Fraud Policy

The system implements the challenge's investigation policy using deterministic rules.

Actions include:

| Action                    | Description                                  |
| ------------------------- | -------------------------------------------- |
| `ALLOW_TRANSACTION`       | Allow the flagged transaction to stand       |
| `DECLINE_TRANSACTION`     | Decline the flagged authorization            |
| `MONITOR_CARD`            | Increase monitoring sensitivity              |
| `MONITOR_CONNECTED_CARDS` | Monitor connected cards                      |
| `WARN_CUSTOMER`           | Send an informational customer message       |
| `VERIFY_WITH_CUSTOMER`    | Ask the cardholder to verify the transaction |
| `STEP_UP_AUTH`            | Require additional authentication            |
| `BLOCK_CARD`              | Block and reissue the card                   |
| `BLOCK_ALL_CARDS`         | Block all cards belonging to the customer    |
| `GENERATE_REPORT`         | Generate an internal investigation report    |
| `CREATE_CASE`             | Create an internal fraud case                |
| `FILE_REPORT`             | File a suspicious activity report            |
| `ESCALATE_TO_ANALYST`     | Escalate to a human analyst                  |
| `CLOSE_NO_FRAUD`          | Close the alert as legitimate                |

The policy also contains approval routing.

For example:

```text
auto
  |
  +-- low-impact operational actions

L1
  |
  +-- selected actions requiring team-lead approval

L2
  |
  +-- high-impact actions / regulatory reporting
```

The agent recommends actions and approval routes according to the policy.

---

# TigerGraph

TigerGraph is the relationship and investigation layer of the system.

Fraud investigations are inherently relational.

A single transaction can be connected to:

```text
Customer
   |
   +--- Card
   |
   +--- Transaction
   |
   +--- Device Profile
   |
   +--- Email Domain
   |
   +--- Billing Region
   |
   +--- Other Transactions
   |
   +--- Historical Fraud Cases
```

This makes graph traversal particularly useful for investigating coordinated activity.

---

# Graph Model

The investigation graph contains entities such as:

### Vertices

```text
Customer
Card
Transaction
DeviceProfile
EmailDomain
BillingRegion
ClosedCase
```

### Relationships

```text
Customer -> OWNS -> Card

Card -> MADE -> Transaction

Transaction -> FROM_DEVICE -> DeviceProfile

Transaction -> PURCHASER_EMAIL -> EmailDomain

Transaction -> BILLED_IN -> BillingRegion

Transaction -> NEXT -> Transaction

ClosedCase -> INVOLVES -> Transaction

ClosedCase -> ON_CARD -> Card

ClosedCase -> CONNECTED_TO -> Card
```

The exact graph implementation can be extended with additional relationship types as the investigation requires.

---

# Why Graphs Matter for Fraud

Traditional transaction-level analysis can miss relationships such as:

```text
Customer A
    |
    +---- Card A
    |
    +---- Device X
             |
             +---- Customer B
             |
             +---- Card B
```

A transaction may appear normal in isolation while its surrounding relationship network reveals suspicious activity.

The agent therefore investigates entities and relationships rather than looking only at the original transaction.

---

# Historical Case Memory

Historical closed investigations provide additional context.

The agent can retrieve previous cases and compare:

* Similar cards
* Similar transactions
* Connected entities
* Fraud patterns
* Historical outcomes
* Previously observed relationships

This provides a case-memory mechanism that can help distinguish isolated anomalies from recurring patterns.

---

# Fraud Patterns

The system supports the challenge's known fraud pattern categories as well as cases where no known pattern is sufficiently supported.

Supported categories include:

```text
card_testing
card_not_present_fraud
card_not_present_new_device
out_of_region_use
account_takeover
undocumented
none
```

The agent is not required to force every investigation into one of the known categories.

If the evidence does not support a known pattern, the investigation can remain uncertain or use the appropriate alternative classification.

---

# Handling Uncertainty

One of the important design goals is avoiding automatic escalation based on a single signal.

For example:

```text
Customer reports transaction
        |
        v
Strong fraud signal
        |
        v
Is the report independently verified?
        |
      No
        |
        v
Remain uncertain
        |
        v
VERIFY_WITH_CUSTOMER
```

A customer report is therefore treated as important evidence, but an unverified report does not automatically become confirmed fraud.

Similarly, a high bank risk score triggers investigation but is not treated as a final fraud verdict.

---

# Evidence Model

The investigation records both supporting and contradicting evidence.

Examples of evidence include:

```text
Transaction history
Customer history
Card relationships
Device relationships
Regional relationships
Email-domain relationships
Historical fraud cases
Risk score
Customer reports
Analyst requests
Connected transactions
```

This allows the final decision to remain explainable.

---

# Next Best Action

The system produces two action sets:

```text
initial
final
```

The initial action represents what should happen at case intake.

The final action represents the recommendation after investigation and any additional evidence gathering.

Example:

```json
{
  "next_best_actions": {
    "initial": [
      {
        "action": "VERIFY_WITH_CUSTOMER",
        "route": "auto",
        "reason": "Customer confirmation is required before resolving the alert."
      }
    ],
    "final": [
      {
        "action": "CREATE_CASE",
        "route": "auto",
        "reason": "Investigation evidence supports continued fraud-case handling."
      }
    ]
  }
}
```

This makes the investigation progression auditable.

---

# SAR Determination

The system also evaluates whether a Suspicious Activity Report should be filed according to the configured investigation policy.

The structured output records:

```text
file
reason
narrative
subjects
total_amount_usd
activity_dates
```

For cases where a SAR is not appropriate, the output explicitly records that the report was not filed and why.

---

# Final Output Contract

Every benchmark case produces a JSON file.

The final submission contains:

```text
cases/
├── HHG-001.json
├── HHG-002.json
├── HHG-003.json
├── HHG-004.json
├── HHG-005.json
├── HHG-006.json
├── HHG-007.json
├── HHG-008.json
├── HHG-009.json
├── HHG-010.json
├── HHG-011.json
├── HHG-012.json
├── HHG-013.json
├── HHG-014.json
├── HHG-015.json
├── HHG-016.json
├── HHG-017.json
├── HHG-018.json
├── HHG-019.json
└── HHG-020.json
```

Each output contains the structured investigation record.

---

# Case Output Structure

A case file follows this general structure:

```json
{
  "case_id": "HHG-001",

  "case": {
    "status": "completed",
    "verdict": "suspected_fraud",
    "fraud_probability": 0.85,
    "pattern": "card_testing",
    "pattern_description": "...",
    "affected_txn_ids": [],
    "first_suspicious_txn_id": "...",
    "connected_card_ids": [],
    "connected_device_profiles": [],
    "exposure_usd": 0,
    "evidence": [],
    "similar_prior_cases": [],
    "summary": "...",
    "written_to_graph": true,
    "graph_case_id": "..."
  },

  "evidence_requests": [],

  "next_best_actions": {
    "initial": [],
    "final": []
  },

  "sar": {
    "file": false,
    "reason": "...",
    "narrative": "",
    "subjects": [],
    "total_amount_usd": 0,
    "activity_dates": []
  },

  "stop_reason": "...",

  "tool_calls": 0,

  "tokens": 0,

  "latency_s": 0.0
}
```

The exact values depend on the investigation.

---

# Example Investigation

## HHG-018 — Uncertain Customer Report

One of the benchmark cases demonstrates why the system does not simply equate a customer complaint with confirmed fraud.

The customer reports that they did not make the transaction.

The investigation treats this as a strong signal, but the response is not automatically considered independently verified.

The system can therefore reach:

```text
Customer Report
      |
      v
Strong Fraud Signal
      |
      v
Independent Verification Required
      |
      v
UNCERTAIN
      |
      v
VERIFY_WITH_CUSTOMER
```

This allows the agent to preserve uncertainty instead of forcing a binary fraud decision.

---

## HHG-020 — Account Takeover Investigation

Another benchmark case demonstrates a stronger fraud assessment.

The system identifies:

```text
Verdict:
suspected_fraud

Pattern:
account_takeover

Fraud Probability:
high

Next Best Action:
policy-driven action
```

The important part is that the final result contains more than a probability.

The case also records the supporting investigation evidence, affected transactions, exposure, connected entities and recommended action.

---

# Legitimate Cases

The system also handles cases where the available evidence supports legitimate activity.

For legitimate cases:

```text
verdict = legitimate
fraud_probability = low
affected_txn_ids = []
exposure_usd = 0
sar.file = false
```

This prevents the system from treating every challenge alert as fraud.

---

# LLM

The current investigation configuration uses:

```text
Provider:
OpenRouter

Model:
Google Gemini 2.5 Flash
```

The LLM is used for:

* Investigation reasoning
* Tool selection
* Hypothesis generation
* Evidence synthesis
* Assessment
* Explanation generation

The deterministic policy layer remains responsible for enforcing operational rules.

---

# Agentic Design

The system uses an iterative investigation process rather than a single LLM call.

A simplified investigation looks like:

```text
Case Trigger
     |
     v
LLM Investigator
     |
     +----> Tool Call
     |         |
     |         v
     |     Evidence
     |         |
     +<--------+
     |
     v
More Evidence Needed?
     |
   +---+
   |   |
  Yes  No
   |   |
   |   v
   | Assessment
   |   |
   +---+
       |
       v
Policy Engine
       |
       v
Final Decision
```

The investigator can therefore adapt its next action based on evidence discovered during the investigation.

---

# Safety and Controls

The architecture separates:

### Probabilistic reasoning

Handled by the LLM:

```text
What might be happening?
What evidence matters?
What hypotheses should be investigated?
```

### Deterministic policy

Handled by the policy engine:

```text
What actions are permitted?
What approval route is required?
When should a case be created?
When can an action be executed automatically?
```

This separation reduces the risk of the LLM directly inventing operational decisions.

---

# Project Structure

The repository is organized approximately as follows:

```text
fraud-agent/
│
├── agent/
│   ├── assessment.py
│   ├── investigator.py
│   ├── orchestrator.py
│   ├── policy.py
│   ├── state.py
│   ├── tool_executor.py
│   ├── llm_config.py
│   ├── llm_engine.py
│   └── evidence_builder.py
│
├── config/
│   └── policy.py
│
├── schemas/
│   ├── decision.py
│   └── output_adapter.py
│
├── tools/
│   ├── transactions.py
│   ├── customers.py
│   ├── cards.py
│   ├── devices.py
│   ├── regions.py
│   ├── closed_cases.py
│   ├── graph.py
│   ├── evidence_requests.py
│   ├── tigergraph_fraud.py
│   └── hhgoa_data.py
│
├── scripts/
│   ├── convert_results_to_cases.py
│   └── validate_cases.py
│
├── tests/
│   ├── test_policy.py
│   ├── test_policy_audit.py
│   ├── test_batch_runner.py
│   ├── test_hhg001_e2e.py
│   ├── test_hhg001_deep_investigation.py
│   ├── test_hhg001_policy_e2e.py
│   └── test_real_llm_agent.py
│
├── cases/
│   ├── HHG-001.json
│   ├── HHG-002.json
│   ├── ...
│   └── HHG-020.json
│
├── results/
│   └── summary.json
│
├── run_all.py
├── requirements.txt
├── .env.example
└── README.md
```

---

# Running the Project

## 1. Clone the repository

```bash
git clone https://github.com/Vanshk08/HACKER-HOUSE-GOA.git
cd HACKER-HOUSE-GOA
```

Navigate to the fraud-agent project directory if required by the repository layout.

---

## 2. Create a virtual environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Configuration

Create a `.env` file based on `.env.example`.

The project uses environment variables for model and graph configuration.

Example:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_api_key
OPENROUTER_MODEL=google/gemini-2.5-flash

TG_HOST=your_tigergraph_host
TG_USERNAME=your_username
TG_PASSWORD=your_password
TG_GRAPH_NAME=your_graph
```

Do not commit API keys or credentials.

---

# Running the Batch Investigation

The batch runner is responsible for discovering the benchmark cases and running the investigation workflow.

Example:

```bash
python run_all.py
```

The runner supports provider configuration and output configuration.

Check available options with:

```bash
python run_all.py --help
```

Example:

```bash
python run_all.py --provider openrouter
```

---

# Validating the Final Cases

The final benchmark files can be validated with:

```bash
python scripts/validate_cases.py
```

The validation checks the structure and required fields of the final case outputs.

The final repository should contain exactly:

```text
HHG-001.json
...
HHG-020.json
```

inside:

```text
cases/
```

---

# Testing

Run the complete test suite with:

```bash
pytest
```

The project includes tests for:

* Policy rules
* Policy precedence
* Policy conflicts
* Case discovery
* Case isolation
* Output formatting
* End-to-end investigation
* Deep investigation
* Evidence gathering
* LLM integration
* Final output validation

The final submission was validated with the project's test suite and case validation tooling.

---

# Demo UI

The frontend is designed as an analyst investigation dashboard.

The main dashboard displays:

```text
Case
 |
 +-- Fraud Probability
 |
 +-- Investigation Verdict
 |
 +-- Pattern Classification
 |
 +-- Next Best Action
 |
 +-- SAR Determination
 |
 +-- Evidence
 |
 +-- TigerGraph Relationships
```

The UI supports reviewing the precomputed results for all 20 challenge cases.

---

# Investigation Dashboard

The dashboard provides:

### Case navigation

```text
HHG-001
HHG-002
...
HHG-020
```

### Investigation summary

```text
Fraud Probability
Investigation Verdict
Pattern
Exposure
```

### Next Best Action

The UI displays both the operational recommendation and its approval route.

### Evidence

Evidence is grouped by categories such as:

```text
Verified Evidence
Customer Outreach
Transaction
Customer
Cards
```

### Graph visualization

The TigerGraph visualization shows relationships between entities such as:

```text
Case
Transaction
Customer
Card
Email Domain
Device / Region
Historical relationships
```

---

# Explainability

The final case output is designed to answer:

### What happened?

The case summary describes the investigation.

### Why is it suspicious?

The evidence field records relevant supporting signals.

### What contradicts the hypothesis?

The assessment can preserve contradicting evidence and uncertainty.

### How far does it go?

The system records affected transactions, connected cards and related entities.

### What should happen next?

The policy engine produces the next-best action.

### Who needs to approve it?

The action includes the relevant approval route.

---

# Design Principles

## 1. Risk score is not a verdict

A high risk score starts an investigation.

It does not automatically mean fraud.

---

## 2. Evidence before escalation

The system attempts to gather supporting evidence before making high-impact decisions.

---

## 3. Graph relationships matter

Fraud can be distributed across:

```text
Customers
Cards
Transactions
Devices
Regions
Email domains
```

Graph traversal helps expose these relationships.

---

## 4. Preserve uncertainty

When evidence is incomplete or contradictory, the system can return:

```text
uncertain
```

instead of forcing a fraud/legitimate classification.

---

## 5. Separate reasoning from policy

The LLM investigates and reasons.

The deterministic policy engine controls operational decisions.

---

## 6. Keep the final output auditable

Every case contains structured evidence, actions, decisions and metadata.

---

# Output Validation

Before submission, the final case set is checked to ensure:

```text
20 cases exist
|
+-- HHG-001
+-- HHG-002
+-- ...
+-- HHG-020
```

and that every case conforms to the expected output structure.

This makes the benchmark output reproducible and machine-readable.

---

# Technologies

| Component           | Technology                         |
| ------------------- | ---------------------------------- |
| Agent framework     | LangGraph                          |
| LLM                 | Google Gemini 2.5 Flash            |
| LLM provider        | OpenRouter                         |
| Graph database      | TigerGraph                         |
| Graph queries       | TigerGraph / GSQL tooling          |
| Backend             | Python                             |
| Agent orchestration | LangGraph StateGraph               |
| Policy              | Deterministic Python policy engine |
| Output              | JSON                               |
| Testing             | Pytest                             |
| Frontend            | Analyst investigation dashboard    |

---

# What Makes the System Agentic?

The system is not simply:

```text
Transaction -> LLM -> Fraud Score
```

Instead it follows:

```text
Trigger
  |
  v
Reason about what to investigate
  |
  v
Select tools
  |
  v
Query connected evidence
  |
  v
Generate / update hypotheses
  |
  v
Assess evidence
  |
  v
Determine whether uncertainty remains
  |
  +----> Request additional evidence
  |
  v
Apply deterministic policy
  |
  v
Recommend next action
  |
  v
Produce auditable case
```

This allows the investigation process to adapt based on what it discovers.

---

# Limitations

This project is a hackathon investigation system and should not be interpreted as a production banking fraud system.

In particular:

* Customer responses may be unavailable and therefore remain explicitly unknown.
* Some investigation actions are represented or simulated rather than connected to real banking systems.
* The benchmark dataset is anonymized.
* The LLM remains probabilistic.
* Production deployment would require stronger authentication, authorization, monitoring, audit infrastructure, model governance and regulatory controls.

---

# Future Improvements

With additional development time, the system could be extended with:

### Continuous investigation

Automatically monitor new transaction alerts and initiate investigations.

### Better graph algorithms

Use graph centrality, community detection and connected-component analysis to identify coordinated fraud rings.

### More sophisticated GraphRAG

Combine graph traversal with semantic retrieval from:

* Fraud policies
* Historical investigations
* Regulatory documents
* Analyst notes

### Human-in-the-loop investigation

Allow analysts to:

```text
Approve
Reject
Request evidence
Override recommendation
Close case
```

and write the resulting decision back into case memory.

### Learning from resolved cases

Use resolved investigations to improve future evidence retrieval and recommendations.

### Production integrations

Connect the agent to:

```text
Transaction monitoring
Customer identity systems
Authentication systems
Case management
CRM
Notification systems
Regulatory reporting
```

---

# Security

Never commit:

```text
.env
API keys
TigerGraph credentials
OpenRouter credentials
Customer credentials
Production secrets
```

Use `.env.example` for configuration templates.

---

# Dataset Attribution

The challenge dataset is based on the **IEEE-CIS Fraud Detection** dataset published by Vesta Corporation through the IEEE Computational Intelligence Society.

The Hacker House Goa challenge adds the investigation-specific entities, case information, risk scores, historical cases and benchmark cases.

The challenge dataset is anonymized.

No real customer identities are used by this project.

---

# Challenge Compliance

The project provides:

* A working fraud investigation workflow
* TigerGraph-based relationship investigation
* Agentic investigation and evidence gathering
* Next-best-action recommendations
* Policy-driven decisions
* Case memory / historical case retrieval
* Structured investigation outputs
* 20 benchmark case files
* Investigation UI
* Evidence visualization
* TigerGraph relationship visualization

---

# Final Submission

The benchmark outputs are located in:

```text
cases/
```

with exactly:

```text
HHG-001.json
HHG-002.json
HHG-003.json
HHG-004.json
HHG-005.json
HHG-006.json
HHG-007.json
HHG-008.json
HHG-009.json
HHG-010.json
HHG-011.json
HHG-012.json
HHG-013.json
HHG-014.json
HHG-015.json
HHG-016.json
HHG-017.json
HHG-018.json
HHG-019.json
HHG-020.json
```

---

# Team

**Manob Raj Saikia**

Hacker House Goa 2026

---

# Summary

This project demonstrates an agentic approach to fraud investigation where:

```text
                    ┌─────────────────┐
                    │  Suspicious      │
                    │  Transaction     │
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │    LangGraph    │
                    │   Investigator  │
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │   TigerGraph    │
                    │    Evidence     │
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │    Assessment   │
                    │  + Hypotheses   │
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │ Deterministic   │
                    │ Policy Engine   │
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │ Next Best       │
                    │ Action          │
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │ Auditable Case  │
                    │   HHG-XXX.json  │
                    └─────────────────┘
```

The goal is not simply to predict fraud.

The goal is to **investigate it, gather evidence, understand relationships, preserve uncertainty when necessary, apply explicit policy, and produce an auditable decision.**

```

ile the challenge's original README remains the specification you built against. 
```
