// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title AgentRegistry
/// @notice On-chain registry for AI agents. Any agent can register itself
///         with a list of capabilities, a price-per-task, and an endpoint URL.
contract AgentRegistry {

    // ─────────────────────────────────────────────
    // Types
    // ─────────────────────────────────────────────

    struct Agent {
        bytes32  agentId;       // keccak256(owner + name)
        address  owner;         // EOA / contract that registered
        string   name;
        string   description;
        string[] capabilities;  // e.g. ["summarization","web-search"]
        string   endpointUrl;   // REST endpoint the agent listens on
        uint256  pricePerTask;  // wei per task
        bool     active;
        uint256  registeredAt;
        uint256  taskCount;     // updated by TaskEscrow
    }

    // ─────────────────────────────────────────────
    // Storage
    // ─────────────────────────────────────────────

    mapping(bytes32 => Agent)   private agents;
    bytes32[]                   private agentIds;

    address public taskEscrow;  // set once by deployer

    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────

    event AgentRegistered(bytes32 indexed agentId, address indexed owner, string name);
    event AgentUpdated   (bytes32 indexed agentId);
    event AgentDeactivated(bytes32 indexed agentId);
    event TaskEscrowSet  (address escrow);

    // ─────────────────────────────────────────────
    // Modifiers
    // ─────────────────────────────────────────────

    modifier onlyAgentOwner(bytes32 agentId) {
        require(agents[agentId].owner == msg.sender, "Not agent owner");
        _;
    }

    modifier onlyEscrow() {
        require(msg.sender == taskEscrow, "Only TaskEscrow");
        _;
    }

    // ─────────────────────────────────────────────
    // Admin
    // ─────────────────────────────────────────────

    address public immutable deployer;
    constructor() { deployer = msg.sender; }

    function setTaskEscrow(address _escrow) external {
        require(msg.sender == deployer, "Only deployer");
        require(taskEscrow == address(0), "Already set");
        taskEscrow = _escrow;
        emit TaskEscrowSet(_escrow);
    }

    // ─────────────────────────────────────────────
    // Core
    // ─────────────────────────────────────────────

    function registerAgent(
        string  calldata name,
        string  calldata description,
        string[] calldata capabilities,
        string  calldata endpointUrl,
        uint256 pricePerTask
    ) external returns (bytes32 agentId) {
        agentId = keccak256(abi.encodePacked(msg.sender, name));
        require(agents[agentId].owner == address(0), "Agent already exists");
        require(bytes(name).length > 0,        "Name required");
        require(bytes(endpointUrl).length > 0, "Endpoint required");

        agents[agentId] = Agent({
            agentId:      agentId,
            owner:        msg.sender,
            name:         name,
            description:  description,
            capabilities: capabilities,
            endpointUrl:  endpointUrl,
            pricePerTask: pricePerTask,
            active:       true,
            registeredAt: block.timestamp,
            taskCount:    0
        });

        agentIds.push(agentId);
        emit AgentRegistered(agentId, msg.sender, name);
    }

    function updateAgent(
        bytes32 agentId,
        string  calldata description,
        string[] calldata capabilities,
        string  calldata endpointUrl,
        uint256 pricePerTask
    ) external onlyAgentOwner(agentId) {
        Agent storage a = agents[agentId];
        a.description  = description;
        a.capabilities = capabilities;
        a.endpointUrl  = endpointUrl;
        a.pricePerTask = pricePerTask;
        emit AgentUpdated(agentId);
    }

    function deactivateAgent(bytes32 agentId) external onlyAgentOwner(agentId) {
        agents[agentId].active = false;
        emit AgentDeactivated(agentId);
    }

    // Called by TaskEscrow when a task is completed
    function incrementTaskCount(bytes32 agentId) external onlyEscrow {
        agents[agentId].taskCount++;
    }

    // ─────────────────────────────────────────────
    // Views
    // ─────────────────────────────────────────────

    function getAgent(bytes32 agentId) external view returns (Agent memory) {
        return agents[agentId];
    }

    function getAllAgentIds() external view returns (bytes32[] memory) {
        return agentIds;
    }

    function getActiveAgents() external view returns (Agent[] memory) {
        uint256 count;
        for (uint256 i; i < agentIds.length; i++) {
            if (agents[agentIds[i]].active) count++;
        }
        Agent[] memory result = new Agent[](count);
        uint256 idx;
        for (uint256 i; i < agentIds.length; i++) {
            if (agents[agentIds[i]].active) result[idx++] = agents[agentIds[i]];
        }
        return result;
    }
}
