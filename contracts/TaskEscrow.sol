// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./AgentRegistry.sol";

/// @title TaskEscrow
/// @notice Agent A posts a task with locked ETH → Agent B accepts & delivers
///         → ETH is released automatically after verification window.
///         Dispute during window sends funds to a fee collector for arbitration.
contract TaskEscrow {

    // ─────────────────────────────────────────────
    // Types
    // ─────────────────────────────────────────────

    enum TaskStatus {
        Open,       // posted, waiting for executor
        Accepted,   // executor claimed the task
        Submitted,  // executor submitted result
        Completed,  // payer approved / timeout passed
        Disputed,   // payer disputed the result
        Cancelled   // payer cancelled before acceptance
    }

    struct Task {
        bytes32     taskId;
        address     payer;          // Agent A (or human)
        bytes32     payerAgentId;   // registry id of payer agent (0 = human)
        bytes32     executorAgentId;// registry id of executor
        address     executorOwner;  // EOA of executor agent owner
        string      taskType;       // e.g. "summarization"
        string      inputData;      // JSON payload
        string      resultData;     // filled by executor
        uint256     payment;        // locked ETH (wei)
        uint256     deadline;       // unix timestamp
        uint256     submittedAt;
        TaskStatus  status;
        uint256     verifyWindow;   // seconds after submission before auto-complete
    }

    // ─────────────────────────────────────────────
    // Storage
    // ─────────────────────────────────────────────

    AgentRegistry public immutable registry;
    address       public immutable feeCollector;
    uint256       public constant  FEE_BPS     = 100; // 1 % protocol fee
    uint256       public constant  VERIFY_WINDOW = 1 hours;

    mapping(bytes32 => Task) private tasks;
    bytes32[]                private taskIds;

    uint256 private _nonce;

    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────

    event TaskCreated   (bytes32 indexed taskId, address indexed payer, string taskType, uint256 payment);
    event TaskAccepted  (bytes32 indexed taskId, bytes32 indexed executorAgentId);
    event TaskSubmitted (bytes32 indexed taskId, string resultData);
    event TaskCompleted (bytes32 indexed taskId, address indexed executor, uint256 payout);
    event TaskDisputed  (bytes32 indexed taskId);
    event TaskCancelled (bytes32 indexed taskId);

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    constructor(address _registry, address _feeCollector) {
        registry     = AgentRegistry(_registry);
        feeCollector = _feeCollector;
    }

    // ─────────────────────────────────────────────
    // Payer actions
    // ─────────────────────────────────────────────

    /// @notice Create a task and lock ETH in escrow
    function createTask(
        bytes32 payerAgentId,
        string  calldata taskType,
        string  calldata inputData,
        uint256 deadline,
        uint256 verifyWindow
    ) external payable returns (bytes32 taskId) {
        require(msg.value > 0,            "Payment required");
        require(deadline > block.timestamp, "Deadline in past");

        taskId = keccak256(abi.encodePacked(msg.sender, _nonce++, block.timestamp));

        tasks[taskId] = Task({
            taskId:          taskId,
            payer:           msg.sender,
            payerAgentId:    payerAgentId,
            executorAgentId: bytes32(0),
            executorOwner:   address(0),
            taskType:        taskType,
            inputData:       inputData,
            resultData:      "",
            payment:         msg.value,
            deadline:        deadline,
            submittedAt:     0,
            status:          TaskStatus.Open,
            verifyWindow:    verifyWindow == 0 ? VERIFY_WINDOW : verifyWindow
        });

        taskIds.push(taskId);
        emit TaskCreated(taskId, msg.sender, taskType, msg.value);
    }

    /// @notice Cancel an open task and reclaim ETH
    function cancelTask(bytes32 taskId) external {
        Task storage t = tasks[taskId];
        require(t.payer == msg.sender,          "Not payer");
        require(t.status == TaskStatus.Open,    "Not open");
        t.status = TaskStatus.Cancelled;
        _transfer(msg.sender, t.payment);
        emit TaskCancelled(taskId);
    }

    /// @notice Approve submitted result — releases ETH to executor
    function approveResult(bytes32 taskId) external {
        Task storage t = tasks[taskId];
        require(t.payer == msg.sender,              "Not payer");
        require(t.status == TaskStatus.Submitted,   "Not submitted");
        _settle(taskId, t);
    }

    /// @notice Dispute submitted result within the verify window
    function disputeTask(bytes32 taskId) external {
        Task storage t = tasks[taskId];
        require(t.payer == msg.sender,              "Not payer");
        require(t.status == TaskStatus.Submitted,   "Not submitted");
        require(block.timestamp < t.submittedAt + t.verifyWindow, "Window passed");
        t.status = TaskStatus.Disputed;
        // send funds to fee collector for manual/DAO arbitration
        _transfer(feeCollector, t.payment);
        emit TaskDisputed(taskId);
    }

    // ─────────────────────────────────────────────
    // Executor actions
    // ─────────────────────────────────────────────

    /// @notice Executor agent claims an open task
    function acceptTask(bytes32 taskId, bytes32 executorAgentId) external {
        Task storage t = tasks[taskId];
        require(t.status == TaskStatus.Open,        "Not open");
        require(block.timestamp < t.deadline,       "Expired");

        AgentRegistry.Agent memory agent = registry.getAgent(executorAgentId);
        require(agent.owner == msg.sender,          "Not agent owner");
        require(agent.active,                       "Agent inactive");

        t.executorAgentId = executorAgentId;
        t.executorOwner   = msg.sender;
        t.status          = TaskStatus.Accepted;
        emit TaskAccepted(taskId, executorAgentId);
    }

    /// @notice Executor submits result (stored on-chain as JSON string / IPFS CID)
    function submitResult(bytes32 taskId, string calldata resultData) external {
        Task storage t = tasks[taskId];
        require(t.executorOwner == msg.sender,      "Not executor");
        require(t.status == TaskStatus.Accepted,    "Not accepted");
        require(block.timestamp < t.deadline,       "Expired");

        t.resultData  = resultData;
        t.submittedAt = block.timestamp;
        t.status      = TaskStatus.Submitted;
        emit TaskSubmitted(taskId, resultData);
    }

    // ─────────────────────────────────────────────
    // Anyone can call — auto-complete after window
    // ─────────────────────────────────────────────

    function claimCompletion(bytes32 taskId) external {
        Task storage t = tasks[taskId];
        require(t.status == TaskStatus.Submitted,   "Not submitted");
        require(block.timestamp >= t.submittedAt + t.verifyWindow, "Window not passed");
        _settle(taskId, t);
    }

    // ─────────────────────────────────────────────
    // Internal
    // ─────────────────────────────────────────────

    function _settle(bytes32 taskId, Task storage t) internal {
        t.status = TaskStatus.Completed;
        uint256 fee    = (t.payment * FEE_BPS) / 10_000;
        uint256 payout = t.payment - fee;
        _transfer(feeCollector,  fee);
        _transfer(t.executorOwner, payout);
        registry.incrementTaskCount(t.executorAgentId);
        emit TaskCompleted(taskId, t.executorOwner, payout);
    }

    function _transfer(address to, uint256 amount) internal {
        (bool ok,) = to.call{value: amount}("");
        require(ok, "ETH transfer failed");
    }

    // ─────────────────────────────────────────────
    // Views
    // ─────────────────────────────────────────────

    function getTask(bytes32 taskId) external view returns (Task memory) {
        return tasks[taskId];
    }

    function getOpenTasks() external view returns (Task[] memory) {
        uint256 count;
        for (uint256 i; i < taskIds.length; i++) {
            if (tasks[taskIds[i]].status == TaskStatus.Open) count++;
        }
        Task[] memory result = new Task[](count);
        uint256 idx;
        for (uint256 i; i < taskIds.length; i++) {
            if (tasks[taskIds[i]].status == TaskStatus.Open) result[idx++] = tasks[taskIds[i]];
        }
        return result;
    }

    function getAllTasks() external view returns (Task[] memory) {
        Task[] memory result = new Task[](taskIds.length);
        for (uint256 i; i < taskIds.length; i++) {
            result[i] = tasks[taskIds[i]];
        }
        return result;
    }
}
