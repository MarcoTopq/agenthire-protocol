"""
Agent B — Data Fetcher
Specialization: web-search / data gathering
Port: 8002
"""
import json, uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI(title="AgentB - Data Fetcher", version="1.0.0")

CAPABILITIES = ["web-search", "data-fetch", "url-scrape"]
PRICE_ETH    = 0.001

# ── Models ────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    taskId:   str = ""
    taskType: str
    input:    dict
    budgetEth: float = 0.001

class TaskResponse(BaseModel):
    taskId: str
    status: str
    output: dict
    proof:  str

# ── Health ────────────────────────────────────────────────────────
@app.get("/")
def info():
    return {
        "agent":        "AgentB-DataFetcher",
        "capabilities": CAPABILITIES,
        "priceEth":     PRICE_ETH,
        "status":       "ready"
    }

# ── Core task handler ─────────────────────────────────────────────
@app.post("/agent/task", response_model=TaskResponse)
async def handle_task(req: TaskRequest):
    task_id = req.taskId or str(uuid.uuid4())

    if req.taskType == "web-search":
        query   = req.input.get("query", "")
        results = await _simulate_search(query)
        output  = {"query": query, "results": results, "count": len(results)}

    elif req.taskType == "data-fetch":
        url  = req.input.get("url", "")
        data = await _fetch_url(url)
        output = {"url": url, "content": data}

    else:
        raise HTTPException(400, f"Unsupported taskType: {req.taskType}")

    import hashlib, json as _json
    proof = "0x" + hashlib.sha256(_json.dumps(output).encode()).hexdigest()
    return TaskResponse(taskId=task_id, status="completed", output=output, proof=proof)


# ── Simulated search (replace w/ real API key in prod) ───────────
async def _simulate_search(query: str) -> list:
    """Returns simulated search snippets — swap for DuckDuckGo / Brave API."""
    return [
        {
            "title":   f"Result 1 for: {query}",
            "snippet": f"This document discusses key aspects of '{query}' "
                       "including history, current state, and future outlook.",
            "url":     "https://example.com/1"
        },
        {
            "title":   f"Result 2 for: {query}",
            "snippet": f"A comprehensive overview of '{query}' with data "
                       "sourced from multiple authoritative publications.",
            "url":     "https://example.com/2"
        },
        {
            "title":   f"Result 3 for: {query}",
            "snippet": f"Latest developments in '{query}' — updated March 2026.",
            "url":     "https://example.com/3"
        },
    ]

async def _fetch_url(url: str) -> str:
    if not url:
        return ""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            return r.text[:2000]  # cap at 2k chars
    except Exception as e:
        return f"[fetch error: {e}]"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
