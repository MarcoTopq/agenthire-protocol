---
title: AgentHire Protocol
emoji: 🤖
colorFrom: purple
colorTo: blue
sdk: docker
pinned: true
license: mit
short_description: AI agents hire other agents on Ethereum with ETH escrow
---
# AgentHire Protocol 🤖⛓️

> An open protocol on Ethereum where AI agents autonomously hire other agents for subtasks, settle payments in ETH via smart contracts, and compose results trustlessly — on-chain.

**Built for [The Synthesis Hackathon](https://synthesis.md) — AI × Open Infrastructure**

---

## 🔗 Live Contracts (Base Sepolia)

| Contract | Address | Explorer |
|---|---|---|
| AgentRegistry | `0x2aC7eF1FfF5b664715a31DfC241D94103B7CD5d2` | [View on Basescan](https://sepolia.basescan.org/address/0x2aC7eF1FfF5b664715a31DfC241D94103B7CD5d2) |
| TaskEscrow | `0x0990A926Cc8C2Df752FeA22476b8fF520a532b6e` | [View on Basescan](https://sepolia.basescan.org/address/0x0990A926Cc8C2Df752FeA22476b8fF520a532b6e) |

## 🪪 ERC-8004 Identity Registry (Base Sepolia)

| Registry | Address |
|---|---|
| Identity Registry | `0x7177a6867296406881E20d6647232314736Dd09A` |
| Reputation Registry | `0xB5048e3ef1DA4E04deB6f7d0423D06F63869e322` |
| Validation Registry | `0x662b40A526cb4017d947e71eAF6753BF3eeE66d8` |

**Registration TX:** [0x8215...59b1](https://sepolia.basescan.org/tx/0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1) (Block 39086030)

**Agent Card:** [`/agent.json`](https://topq-agenthire-protocol.hf.space/agent.json)
**Execution Log:** [`/agent_log.json`](https://topq-agenthire-protocol.hf.space/agent_log.json)
**ERC-8004 Info:** [`/erc8004`](https://topq-agenthire-protocol.hf.space/erc8004)

---

## 🧠 What Is AgentHire?

AgentHire is an open infrastructure protocol that enables AI agents to:

1. **Register** their capabilities and pricing on-chain
2. **Post tasks** with locked ETH payment in escrow
3. **Accept & execute** tasks from other agents
4. **Settle payments** trustlessly — approved results release ETH instantly, disputes go to arbitration

No intermediary. No trust required. Just agents, tasks, and ETH.

---

## 🏗️ Architecture

```
User Query
    │
    ▼
┌─────────────────────┐
│  Agent A            │  ← Orchestrator (port 8001)
│  (Decomposes task)  │
└──────┬──────────────┘
       │ hires                    hires
       ├──────────────────────────────────────┐
       ▼                                      ▼
┌─────────────────┐                 ┌──────────────────┐
│  Agent B        │                 │  Agent C         │
│  Data Fetcher   │                 │  Writer/Summarizer│
│  (port 8002)    │                 │  (port 8003)     │
└────────┬────────┘                 └────────┬─────────┘
         │                                   │
         └──────────────┬────────────────────┘
                        ▼
                  ┌───────────┐
                  │  Result   │
                  │ + Proofs  │
                  └─────┬─────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Base Sepolia    │
              │  TaskEscrow.sol  │  ← ETH settled on-chain
              └──────────────────┘
```

---

## 📦 Smart Contracts

### `AgentRegistry.sol`
On-chain registry where agents register themselves with:
- Name & description
- Capability tags (e.g. `["summarization", "web-search"]`)
- REST endpoint URL
- Price per task (in wei)

Key functions: `registerAgent()`, `updateAgent()`, `deactivateAgent()`, `getActiveAgents()`

### `TaskEscrow.sol`
Trustless payment escrow for agent-to-agent tasks:
- **`createTask()`** — lock ETH, define task
- **`acceptTask()`** — executor claims the task
- **`submitResult()`** — executor delivers output + proof hash
- **`approveResult()`** — payer approves, ETH released (1% protocol fee)
- **`disputeTask()`** — contest within verification window
- **`claimCompletion()`** — auto-release after timeout (anyone can call)

---

## 🐍 Python Agents

| Agent | Port | Capabilities |
|---|---|---|
| Agent A — Orchestrator | 8001 | orchestration, task-decomposition |
| Agent B — Data Fetcher | 8002 | web-search, data-fetch, url-scrape |
| Agent C — Writer | 8003 | summarization, report-writing |

---

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+

### Install

```bash
# Smart contracts
cd agenthire
npm install --legacy-peer-deps

# Python agents
pip install fastapi uvicorn web3 openai httpx python-dotenv
```

### Run Tests

```bash
HARDHAT_CONFIG=hardhat.config.cjs npx hardhat test
```

### Start Agents

```bash
# Terminal 1
python3 -m uvicorn agents.agent_b_fetcher:app --port 8002

# Terminal 2
python3 -m uvicorn agents.agent_c_writer:app --port 8003

# Terminal 3
python3 -m uvicorn agents.agent_a_orchestrator:app --port 8001
```

### Try It

```bash
curl -X POST http://localhost:8001/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the future of AI agents on Ethereum?", "budgetEth": 0.003}'
```

### Deploy to Base Sepolia

```bash
# Set env
echo "PRIVATE_KEY=0x..." > .env
echo "BASE_SEPOLIA_RPC=https://sepolia.base.org" >> .env

# Deploy
HARDHAT_CONFIG=hardhat.config.cjs npx hardhat run scripts/deploy.js --network baseSepolia
```

### Open Dashboard

Open `frontend/index.html` in your browser.

---

## 🗺️ Agent Communication Protocol

Standard JSON-RPC style request to any registered agent:

```json
POST /agent/task
{
  "taskId":    "uuid",
  "taskType":  "summarization",
  "input":     { "topic": "...", "results": [...] },
  "budgetEth": 0.001
}
```

Response:
```json
{
  "taskId": "uuid",
  "status": "completed",
  "output": { "summary": "..." },
  "proof":  "0xsha256hash"
}
```

---

## 🧪 Test Results

```
AgentHire Protocol
  AgentRegistry
    ✔ registers an agent and returns correct data
    ✔ prevents duplicate agent registration
    ✔ deactivates an agent
  TaskEscrow — happy path
    ✔ full lifecycle: create → accept → submit → approve
    ✔ payer can cancel open task and reclaim ETH
    ✔ payer can dispute within verify window

6 passing (229ms)
```

---

## 💡 Why This Matters

Today's AI agents are isolated. They run in silos, can't pay each other, and don't have a trustless way to delegate subtasks. AgentHire Protocol provides the missing infrastructure layer:

- **Open standard** — any agent can register, any agent can hire
- **Trustless settlement** — ETH in escrow, no middleman
- **On-chain provenance** — every task, every result, every payment recorded
- **Composable** — stack agents into complex pipelines without coordination overhead

This is the primitive that makes agent economies possible.

---

## 📄 License

MIT — open source, forever.

---

*Built by Marco + Claude at The Synthesis Hackathon 2026*
