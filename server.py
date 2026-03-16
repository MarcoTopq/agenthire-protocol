"""
AgentHire Protocol — Combined Server
Runs Agent A (Orchestrator), B (Fetcher), C (Writer) as a single app.
Deploy to Render, Railway, or any Python host.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import all sub-apps
from agents.agent_a_orchestrator import app as app_a
from agents.agent_b_fetcher import app as app_b
from agents.agent_c_writer import app as app_c

# Override peer URLs — use PORT env var so it works on HF (7860) and local (8000)
import agents.agent_a_orchestrator as _a
_PORT = os.getenv("PORT", "7860")
_a.AGENT_B_URL = os.getenv("AGENT_B_URL", f"http://localhost:{_PORT}/b")
_a.AGENT_C_URL = os.getenv("AGENT_C_URL", f"http://localhost:{_PORT}/c")

app = FastAPI(
    title="AgentHire Protocol — API",
    description="Open protocol for AI agent-to-agent task delegation with ETH settlement",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount sub-apps
app.mount("/a", app_a)
app.mount("/b", app_b)
app.mount("/c", app_c)

@app.get("/")
def root():
    return {
        "protocol": "AgentHire",
        "version": "1.0.0",
        "network": "Base Sepolia",
        "contracts": {
            "registry": "0x2aC7eF1FfF5b664715a31DfC241D94103B7CD5d2",
            "escrow":   "0x0990A926Cc8C2Df752FeA22476b8fF520a532b6e"
        },
        "agents": {
            "orchestrator": "/a",
            "fetcher":      "/b",
            "writer":       "/c"
        },
        "endpoints": {
            "orchestrate": "POST /a/orchestrate",
            "status":      "GET  /a/status",
            "agentB":      "POST /b/agent/task",
            "agentC":      "POST /c/agent/task"
        }
    }

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
