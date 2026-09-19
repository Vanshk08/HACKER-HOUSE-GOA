# HACKER-HOUSE-GOA

## AI-Assisted Fraud Investigation System

A graph-based fraud investigation system built for the hackathon.

The system uses TigerGraph to model transaction relationships and an MCP server to expose fraud investigation capabilities to an AI agent.

---

## Architecture

```text
                    ┌──────────────────────┐
                    │      User / Agent    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     MCP Server       │
                    │ analyze_transaction()│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    FraudAnalyzer     │
                    │                      │
                    │ • Risk scoring       │
                    │ • Fraud signals      │
                    │ • Graph evidence     │
                    │ • Explainability     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ TigerGraph Client    │
                    └──────────┬───────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │       TigerGraph Cloud         │
              │                                │
              │ Payment_Transaction             │
              │ Card                           │
              │ Merchant / Community           │
              │                                │
              │ Card_Send_Transaction          │
              └────────────────────────────────┘