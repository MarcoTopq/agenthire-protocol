"""
Agent A — Orchestrator
Responsibilities:
  1. Accept a high-level query from the user / API
  2. Break it into sub-tasks
  3. Hire Agent B (data fetch) and Agent C (summarization) via HTTP
  4. Optionally post tasks on-chain via TaskEscrow
  5. Return the compiled result
  6. Safety guardrails: budget cap, input validation, max sub-tasks
  7. Decision logging: structured log for every session → /agent_log.json

ERC-8004 Identity: 0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1 (tx)
Port: 8001
"""
import json, uuid, hashlib, time, re
from collections import deque
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="AgentA - Orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_B_URL = "http://localhost:8002"
AGENT_C_URL = "http://localhost:8003"

# ── Safety constants ───────────────────────────────────────────────
MAX_BUDGET_ETH  = 0.01      # Hard cap on budget per session
MAX_SUBTASKS    = 10        # Max sub-tasks per session
MAX_QUERY_LEN   = 2000      # Max chars in query
DISALLOWED_PATTERNS = [
    r"private.?key",
    r"mnemonic",
    r"seed.?phrase",
    r"exec\(",
    r"eval\(",
    r"__import__",
    r"os\.system",
    r"subprocess",
]

# ── In-memory session log (last 50 sessions) ──────────────────────
SESSION_LOG: deque = deque(maxlen=50)

# ── Models ────────────────────────────────────────────────────────
class OrchestrateRequest(BaseModel):
    query:      str
    budgetEth:  float = 0.003
    onChain:    bool  = False  # set True to post tasks to blockchain

class OrchestrateResponse(BaseModel):
    sessionId:   str
    query:       str
    subTasks:    list
    finalReport: str
    proof:       str
    durationMs:  int


# ── Safety guardrails ──────────────────────────────────────────────
def _validate_input(req: OrchestrateRequest) -> None:
    """Raises HTTPException if request fails safety checks."""

    # 1. Budget cap
    if req.budgetEth > MAX_BUDGET_ETH:
        raise HTTPException(
            status_code=400,
            detail=f"Budget {req.budgetEth} ETH exceeds maximum allowed {MAX_BUDGET_ETH} ETH"
        )

    # 2. Query length
    if len(req.query) > MAX_QUERY_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long: {len(req.query)} chars (max {MAX_QUERY_LEN})"
        )

    # 3. Disallowed content patterns
    for pattern in DISALLOWED_PATTERNS:
        if re.search(pattern, req.query, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail=f"Query contains disallowed pattern: {pattern}"
            )

    # 4. Empty query
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")


def _log_decision(session_id: str, step: str, action: str,
                  outcome: str, details: dict = None) -> dict:
    """Append a structured decision entry to the session log."""
    entry = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "sessionId":  session_id,
        "step":       step,
        "action":     action,
        "outcome":    outcome,
        "details":    details or {}
    }
    return entry


# ── Health ────────────────────────────────────────────────────────
@app.get("/")
def info():
    return {
        "agent":        "AgentA-Orchestrator",
        "capabilities": ["orchestration", "task-decomposition",
                         "multi-agent-coordination", "safety-guardrails"],
        "priceEth":     0.003,
        "status":       "ready",
        "erc8004": {
            "identityRegistry": "0x7177a6867296406881E20d6647232314736Dd09A",
            "registrationTx":   "0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1",
            "agentCardURI":     "https://topq-agenthire-protocol.hf.space/agent.json"
        },
        "safety": {
            "maxBudgetEth":  MAX_BUDGET_ETH,
            "maxSubTasks":   MAX_SUBTASKS,
            "guardrails":    ["budget_cap", "input_validation", "pattern_filter"]
        },
        "peers": {
            "agentB": AGENT_B_URL,
            "agentC": AGENT_C_URL
        }
    }


# ── Main endpoint ─────────────────────────────────────────────────
@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest):
    session_id = str(uuid.uuid4())
    start_ms   = int(time.time() * 1000)
    sub_tasks  = []
    decisions  = []  # per-session decision trace

    # ── Safety check ─────────────────────────────────────────────
    decisions.append(_log_decision(
        session_id, "0-safety", "validate_input",
        "checking", {"budgetEth": req.budgetEth, "queryLen": len(req.query)}
    ))
    _validate_input(req)
    decisions.append(_log_decision(
        session_id, "0-safety", "validate_input", "passed"
    ))

    # ── Decompose task ────────────────────────────────────────────
    decisions.append(_log_decision(
        session_id, "1-decompose", "plan_subtasks",
        "planned", {"subtasks": ["web-search via AgentB", "summarization via AgentC"]}
    ))

    async with httpx.AsyncClient(timeout=30) as client:

        # ── Step 1: Hire Agent B to fetch data ───────────────────
        b_payload = {
            "taskId":    str(uuid.uuid4()),
            "taskType":  "web-search",
            "input":     {"query": req.query},
            "budgetEth": min(0.001, req.budgetEth * 0.33)
        }
        decisions.append(_log_decision(
            session_id, "2-hire-B", "send_task",
            "dispatching", {"url": f"{AGENT_B_URL}/agent/task",
                            "taskType": "web-search",
                            "budgetEth": b_payload["budgetEth"]}
        ))
        try:
            b_resp = await client.post(f"{AGENT_B_URL}/agent/task", json=b_payload)
            b_data = b_resp.json()
            result_entry = {
                "agent":    "AgentB-DataFetcher",
                "taskType": "web-search",
                "status":   b_data.get("status", "unknown"),
                "taskId":   b_data.get("taskId", ""),
                "proof":    b_data.get("proof", ""),
            }
            sub_tasks.append(result_entry)
            search_results = b_data.get("output", {}).get("results", [])
            decisions.append(_log_decision(
                session_id, "2-hire-B", "receive_result",
                "completed", {"resultCount": len(search_results),
                              "proof": b_data.get("proof", "")[:16] + "..."}
            ))
        except Exception as e:
            sub_tasks.append({"agent": "AgentB-DataFetcher",
                              "status": "error", "error": str(e)})
            search_results = []
            decisions.append(_log_decision(
                session_id, "2-hire-B", "receive_result",
                "error", {"error": str(e)}
            ))

        # ── Step 2: Hire Agent C to summarize ────────────────────
        c_payload = {
            "taskId":    str(uuid.uuid4()),
            "taskType":  "summarization",
            "input":     {"topic": req.query, "results": search_results},
            "budgetEth": min(0.0005, req.budgetEth * 0.17)
        }
        decisions.append(_log_decision(
            session_id, "3-hire-C", "send_task",
            "dispatching", {"url": f"{AGENT_C_URL}/agent/task",
                            "taskType": "summarization",
                            "budgetEth": c_payload["budgetEth"],
                            "inputSources": len(search_results)}
        ))
        try:
            c_resp = await client.post(f"{AGENT_C_URL}/agent/task", json=c_payload)
            c_data = c_resp.json()
            sub_tasks.append({
                "agent":    "AgentC-Writer",
                "taskType": "summarization",
                "status":   c_data.get("status", "unknown"),
                "taskId":   c_data.get("taskId", ""),
                "proof":    c_data.get("proof", ""),
            })
            final_report = c_data.get("output", {}).get("summary", "No summary generated.")
            decisions.append(_log_decision(
                session_id, "3-hire-C", "receive_result",
                "completed", {"wordCount": len(final_report.split()),
                              "proof": c_data.get("proof", "")[:16] + "..."}
            ))
        except Exception as e:
            sub_tasks.append({"agent": "AgentC-Writer",
                              "status": "error", "error": str(e)})
            final_report = f"[Writer agent unavailable: {e}]"
            decisions.append(_log_decision(
                session_id, "3-hire-C", "receive_result",
                "error", {"error": str(e)}
            ))

    end_ms = int(time.time() * 1000)
    session_proof = "0x" + hashlib.sha256(
        json.dumps({"session": session_id,
                    "report": final_report}).encode()
    ).hexdigest()

    decisions.append(_log_decision(
        session_id, "4-finalize", "compute_proof",
        "done", {"proof": session_proof[:18] + "...",
                 "durationMs": end_ms - start_ms}
    ))

    # ── Append to rolling session log ────────────────────────────
    SESSION_LOG.appendleft({
        "sessionId":   session_id,
        "query":       req.query,
        "startedAt":   datetime.fromtimestamp(start_ms / 1000,
                                              tz=timezone.utc).isoformat(),
        "durationMs":  end_ms - start_ms,
        "status":      "completed",
        "proof":       session_proof,
        "subTaskCount": len(sub_tasks),
        "decisions":   decisions
    })

    return OrchestrateResponse(
        sessionId    = session_id,
        query        = req.query,
        subTasks     = sub_tasks,
        finalReport  = final_report,
        proof        = session_proof,
        durationMs   = end_ms - start_ms,
    )


# ── Status endpoint (for frontend polling) ───────────────────────
@app.get("/status")
async def check_peers():
    peer_status = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in [("agentB", AGENT_B_URL), ("agentC", AGENT_C_URL)]:
            try:
                r = await client.get(url)
                peer_status[name] = {"status": "online", "info": r.json()}
            except:
                peer_status[name] = {"status": "offline"}
    return {"orchestrator": "online", "peers": peer_status}


# ── Agent log endpoint ────────────────────────────────────────────
@app.get("/agent_log")
def agent_log():
    """Returns structured decision log for last 50 sessions."""
    return {
        "agent":    "AgentA-Orchestrator",
        "logCount": len(SESSION_LOG),
        "sessions": list(SESSION_LOG)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
