"""
Agent A — Orchestrator
Responsibilities:
  1. Accept a high-level query from the user / API
  2. Break it into sub-tasks
  3. Hire Agent B (data fetch) and Agent C (summarization) via HTTP
  4. Optionally post tasks on-chain via TaskEscrow
  5. Return the compiled result
Port: 8001
"""
import json, uuid, hashlib, time
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

# ── Models ────────────────────────────────────────────────────────
class OrchestrateRequest(BaseModel):
    query:      str
    budgetEth:  float = 0.003
    onChain:    bool  = False  # set True to post tasks to blockchain

class SubTaskLog(BaseModel):
    agentId:  str
    taskType: str
    status:   str
    result:   Optional[dict] = None

class OrchestrateResponse(BaseModel):
    sessionId:  str
    query:      str
    subTasks:   list
    finalReport: str
    proof:      str
    durationMs: int

# ── Health ────────────────────────────────────────────────────────
@app.get("/")
def info():
    return {
        "agent":        "AgentA-Orchestrator",
        "capabilities": ["orchestration", "task-decomposition", "multi-agent-coordination"],
        "priceEth":     0.003,
        "status":       "ready",
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

    async with httpx.AsyncClient(timeout=30) as client:

        # ── Step 1: Hire Agent B to fetch data ───────────────────
        b_payload = {
            "taskId":    str(uuid.uuid4()),
            "taskType":  "web-search",
            "input":     {"query": req.query},
            "budgetEth": 0.001
        }
        try:
            b_resp = await client.post(f"{AGENT_B_URL}/agent/task", json=b_payload)
            b_data = b_resp.json()
            sub_tasks.append({
                "agent":    "AgentB-DataFetcher",
                "taskType": "web-search",
                "status":   b_data.get("status", "unknown"),
                "taskId":   b_data.get("taskId", ""),
                "proof":    b_data.get("proof", ""),
            })
            search_results = b_data.get("output", {}).get("results", [])
        except Exception as e:
            sub_tasks.append({"agent": "AgentB-DataFetcher", "status": "error", "error": str(e)})
            search_results = []

        # ── Step 2: Hire Agent C to summarize ────────────────────
        c_payload = {
            "taskId":    str(uuid.uuid4()),
            "taskType":  "summarization",
            "input":     {"topic": req.query, "results": search_results},
            "budgetEth": 0.0005
        }
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
        except Exception as e:
            sub_tasks.append({"agent": "AgentC-Writer", "status": "error", "error": str(e)})
            final_report = f"[Writer agent unavailable: {e}]"

    end_ms    = int(time.time() * 1000)
    session_proof = "0x" + hashlib.sha256(
        json.dumps({"session": session_id, "report": final_report}).encode()
    ).hexdigest()

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
