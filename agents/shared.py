"""Shared utilities: ABI loading, web3 connection, task helpers."""
import json, os, hashlib, time
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Web3 setup ────────────────────────────────────────────────────
RPC_URL     = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY", "")
w3          = Web3(Web3.HTTPProvider(RPC_URL))

def get_account():
    if PRIVATE_KEY:
        return w3.eth.account.from_key(PRIVATE_KEY)
    return None

# ── Contract helpers ──────────────────────────────────────────────
def load_deployments():
    p = Path(__file__).parent.parent / "deployments.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}

def load_abi(contract_name: str):
    artifacts_dir = Path(__file__).parent.parent / "artifacts/contracts"
    pattern = f"{contract_name}.sol/{contract_name}.json"
    p = artifacts_dir / pattern
    if p.exists():
        return json.loads(p.read_text())["abi"]
    return []

def get_contract(name: str):
    deps = load_deployments()
    addr = deps.get(name.lower().replace("agent","").replace("task","") +
                    ("registry" if "registry" in name.lower() else "escrow"))
    # fallback key names
    if not addr:
        addr = deps.get("registry") if "registry" in name.lower() else deps.get("escrow")
    abi  = load_abi(name)
    if addr and abi:
        return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
    return None

# ── Message format ────────────────────────────────────────────────
def make_task_request(task_type: str, input_data: dict, budget_eth: float = 0.001) -> dict:
    return {
        "taskType":  task_type,
        "input":     input_data,
        "budgetEth": budget_eth,
        "timestamp": int(time.time()),
    }

def make_task_response(task_id: str, output: dict, status: str = "completed") -> dict:
    result_str = json.dumps(output)
    proof = "0x" + hashlib.sha256(result_str.encode()).hexdigest()
    return {
        "taskId": task_id,
        "status": status,
        "output": output,
        "proof":  proof,
    }
