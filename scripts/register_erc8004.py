"""
ERC-8004 Identity Registration Script
Registers AgentHire agents on the ERC-8004 Identity Registry (Base Sepolia).

Identity Registry: 0x7177a6867296406881E20d6647232314736Dd09A
Function: register(string agentURI) returns (uint256 agentId)
"""

import os, json, sys
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Config ────────────────────────────────────────────────────────
RPC_URL     = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

IDENTITY_REGISTRY   = "0x7177a6867296406881E20d6647232314736Dd09A"
REPUTATION_REGISTRY = "0xB5048e3ef1DA4E04deB6f7d0423D06F63869e322"

# ERC-8004 Identity Registry ABI (minimal)
IDENTITY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "agentURI", "type": "string"}
        ],
        "name": "register",
        "outputs": [
            {"internalType": "uint256", "name": "agentId", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
        ],
        "name": "tokenURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "agentId", "type": "uint256"},
            {"indexed": True, "name": "owner",   "type": "address"},
            {"indexed": False,"name": "agentURI","type": "string"}
        ],
        "name": "AgentRegistered",
        "type": "event"
    }
]

AGENT_CARD_URI = "https://topq-agenthire-protocol.hf.space/agent.json"


def main():
    if not PRIVATE_KEY:
        print("ERROR: PRIVATE_KEY not set in .env")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("ERROR: Cannot connect to Base Sepolia")
        sys.exit(1)

    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"Registering from wallet: {account.address}")
    print(f"Balance: {w3.from_wei(w3.eth.get_balance(account.address), 'ether'):.6f} ETH")

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(IDENTITY_REGISTRY),
        abi=IDENTITY_ABI
    )

    print(f"\nRegistering on ERC-8004 Identity Registry...")
    print(f"  URI: {AGENT_CARD_URI}")

    nonce = w3.eth.get_transaction_count(account.address)

    try:
        tx = contract.functions.register(AGENT_CARD_URI).build_transaction({
            "from":     account.address,
            "nonce":    nonce,
            "gas":      200_000,
            "gasPrice": w3.to_wei("0.01", "gwei"),
            "chainId":  84532
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX sent: 0x{tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            print(f"  ✅ Registration SUCCESS")
            print(f"  Block: {receipt.blockNumber}")
            print(f"  Gas used: {receipt.gasUsed}")

            # Try to extract agentId from logs
            try:
                decoded = contract.events.AgentRegistered().process_receipt(receipt)
                if decoded:
                    agent_id = decoded[0]["args"]["agentId"]
                    print(f"  Agent ID (NFT token): {agent_id}")

                    # Save registration data
                    reg_data = {
                        "txHash":   f"0x{tx_hash.hex()}",
                        "agentId":  str(agent_id),
                        "owner":    account.address,
                        "agentURI": AGENT_CARD_URI,
                        "registry": IDENTITY_REGISTRY,
                        "network":  "base-sepolia",
                        "block":    receipt.blockNumber
                    }
                    out_path = Path(__file__).parent.parent / "erc8004_registration.json"
                    with open(out_path, "w") as f:
                        json.dump(reg_data, f, indent=2)
                    print(f"\n  Saved to: {out_path}")
            except Exception as e:
                print(f"  (Could not decode event: {e})")
                # Save minimal data anyway
                reg_data = {
                    "txHash":   f"0x{tx_hash.hex()}",
                    "owner":    account.address,
                    "agentURI": AGENT_CARD_URI,
                    "registry": IDENTITY_REGISTRY,
                    "network":  "base-sepolia",
                    "block":    receipt.blockNumber
                }
                out_path = Path(__file__).parent.parent / "erc8004_registration.json"
                with open(out_path, "w") as f:
                    json.dump(reg_data, f, indent=2)
        else:
            print(f"  ❌ Transaction FAILED (status=0)")
            print(f"  TX: https://sepolia.basescan.org/tx/0x{tx_hash.hex()}")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        # If already registered, that's fine — save a placeholder
        print("\n  Note: Agent may already be registered. Saving placeholder registration file.")
        reg_data = {
            "status":   "already_registered_or_error",
            "error":    str(e),
            "owner":    account.address,
            "agentURI": AGENT_CARD_URI,
            "registry": IDENTITY_REGISTRY,
            "network":  "base-sepolia"
        }
        out_path = Path(__file__).parent.parent / "erc8004_registration.json"
        with open(out_path, "w") as f:
            json.dump(reg_data, f, indent=2)

    print("\nDone.")


if __name__ == "__main__":
    main()
