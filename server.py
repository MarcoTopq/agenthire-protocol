"""
AgentHire Protocol — Combined Server
Runs Agent A (Orchestrator), B (Fetcher), C (Writer) as a single app.
Deploy to Render, Railway, or any Python host.
"""
import os, json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import all sub-apps
from agents.agent_a_orchestrator import app as app_a, SESSION_LOG
from agents.agent_b_fetcher import app as app_b
from agents.agent_c_writer  import app as app_c

# Override peer URLs — use PORT env var so it works on HF (7860) and local (8000)
import agents.agent_a_orchestrator as _a
_PORT = os.getenv("PORT", "7860")
_a.AGENT_B_URL = os.getenv("AGENT_B_URL", f"http://localhost:{_PORT}/b")
_a.AGENT_C_URL = os.getenv("AGENT_C_URL", f"http://localhost:{_PORT}/c")

# Paths
_AGENT_JSON = Path(__file__).parent / "agent.json"
_ERC8004_JSON = Path(__file__).parent / "erc8004_registration.json"

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
        "version":  "1.0.0",
        "network":  "Base Sepolia",
        "erc8004": {
            "identityRegistry": "0x7177a6867296406881E20d6647232314736Dd09A",
            "registrationTx":   "0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1",
            "agentCardURI":     "https://topq-agenthire-protocol.hf.space/agent.json"
        },
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
            "orchestrate":  "POST /a/orchestrate",
            "status":       "GET  /a/status",
            "agentCard":    "GET  /agent.json",
            "agentLog":     "GET  /agent_log.json",
            "erc8004Info":  "GET  /erc8004",
            "agentB":       "POST /b/agent/task",
            "agentC":       "POST /c/agent/task"
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/agent.json")
def agent_card():
    """ERC-8004 / DevSpot Agent Manifest — describes this agent's identity, capabilities & contracts."""
    if _AGENT_JSON.exists():
        with open(_AGENT_JSON) as f:
            data = json.load(f)
        return JSONResponse(content=data, media_type="application/json")
    return JSONResponse(content={"error": "agent.json not found"}, status_code=404)


@app.get("/agent_log.json")
def agent_log_file():
    """Structured execution log: all recent orchestration sessions with decision traces."""
    log_data = {
        "agent":       "AgentHire-Orchestrator",
        "version":     "1.0.0",
        "protocol":    "AgentHire/1.0",
        "erc8004": {
            "identityRegistry": "0x7177a6867296406881E20d6647232314736Dd09A",
            "registrationTx":   "0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1"
        },
        "logCount":    len(SESSION_LOG),
        "sessions":    list(SESSION_LOG)
    }
    return JSONResponse(content=log_data, media_type="application/json")


@app.get("/erc8004")
def erc8004_info():
    """ERC-8004 registration details for this agent."""
    data = {
        "standard":         "ERC-8004",
        "network":          "Base Sepolia (Chain ID: 84532)",
        "operator":         "0xD7d0E5785Fca3021b1f0821932ED4509ec9bfcFF",
        "registrationTx":   "0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1",
        "block":            39086030,
        "registries": {
            "identity":   "0x7177a6867296406881E20d6647232314736Dd09A",
            "reputation": "0xB5048e3ef1DA4E04deB6f7d0423D06F63869e322",
            "validation": "0x662b40A526cb4017d947e71eAF6753BF3eeE66d8"
        },
        "agentCardURI": "https://topq-agenthire-protocol.hf.space/agent.json",
        "basescanTx":   "https://sepolia.basescan.org/tx/0x821511049ab0da8e8083de3b81697d1c3806d8c8a8eedc5e4aa8fccfc90459b1"
    }
    if _ERC8004_JSON.exists():
        with open(_ERC8004_JSON) as f:
            saved = json.load(f)
        data.update(saved)
    return data


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
