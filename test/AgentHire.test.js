import { expect } from "chai";
import hre from "hardhat";
const { ethers } = hre;

describe("AgentHire Protocol", function () {
  let registry, escrow;
  let deployer, agentAOwner, agentBOwner, feeCollector;

  beforeEach(async function () {
    [deployer, agentAOwner, agentBOwner, feeCollector] = await ethers.getSigners();

    const Registry = await ethers.getContractFactory("AgentRegistry");
    registry = await Registry.deploy();
    await registry.waitForDeployment();

    const Escrow = await ethers.getContractFactory("TaskEscrow");
    escrow = await Escrow.deploy(await registry.getAddress(), feeCollector.address);
    await escrow.waitForDeployment();

    await registry.setTaskEscrow(await escrow.getAddress());
  });

  // ──────────────────────────────────────────
  describe("AgentRegistry", function () {
    it("registers an agent and returns correct data", async function () {
      const tx = await registry.connect(agentAOwner).registerAgent(
        "ResearchAgent", "Fetches and summarizes data",
        ["web-search", "summarization"], "http://localhost:8001",
        ethers.parseEther("0.001")
      );
      const receipt = await tx.wait();
      const agentId = receipt.logs[0].args[0];
      const agent   = await registry.getAgent(agentId);
      expect(agent.name).to.equal("ResearchAgent");
      expect(agent.active).to.be.true;
      expect(agent.owner).to.equal(agentAOwner.address);
    });

    it("prevents duplicate agent registration", async function () {
      await registry.connect(agentAOwner).registerAgent("Agent", "", [], "http://x.com", 0);
      await expect(
        registry.connect(agentAOwner).registerAgent("Agent", "", [], "http://x.com", 0)
      ).to.be.revertedWith("Agent already exists");
    });

    it("deactivates an agent", async function () {
      const tx = await registry.connect(agentAOwner).registerAgent("TempAgent", "", [], "http://x.com", 0);
      const agentId = (await tx.wait()).logs[0].args[0];
      await registry.connect(agentAOwner).deactivateAgent(agentId);
      expect((await registry.getAgent(agentId)).active).to.be.false;
    });
  });

  // ──────────────────────────────────────────
  describe("TaskEscrow — happy path", function () {
    let agentAId, agentBId, taskId;
    const payment = ethers.parseEther("0.01");

    beforeEach(async function () {
      let tx = await registry.connect(agentAOwner).registerAgent(
        "AgentA", "Orchestrator", ["orchestration"], "http://a.local", payment
      );
      agentAId = (await tx.wait()).logs[0].args[0];

      tx = await registry.connect(agentBOwner).registerAgent(
        "AgentB", "Writer", ["summarization"], "http://b.local", payment
      );
      agentBId = (await tx.wait()).logs[0].args[0];

      const deadline = Math.floor(Date.now() / 1000) + 3600;
      tx = await escrow.connect(agentAOwner).createTask(
        agentAId, "summarization",
        JSON.stringify({ text: "Summarize Ethereum history" }),
        deadline, 0, { value: payment }
      );
      taskId = (await tx.wait()).logs[0].args[0];
    });

    it("full lifecycle: create → accept → submit → approve", async function () {
      await escrow.connect(agentBOwner).acceptTask(taskId, agentBId);
      expect((await escrow.getTask(taskId)).status).to.equal(1n);

      const result = JSON.stringify({ summary: "Ethereum is a decentralized platform..." });
      await escrow.connect(agentBOwner).submitResult(taskId, result);
      expect((await escrow.getTask(taskId)).status).to.equal(2n);

      const before = await ethers.provider.getBalance(agentBOwner.address);
      await escrow.connect(agentAOwner).approveResult(taskId);
      const after  = await ethers.provider.getBalance(agentBOwner.address);
      expect(after).to.be.gt(before);
      expect((await escrow.getTask(taskId)).status).to.equal(3n);
      expect((await registry.getAgent(agentBId)).taskCount).to.equal(1n);
    });

    it("payer can cancel open task and reclaim ETH", async function () {
      const before = await ethers.provider.getBalance(agentAOwner.address);
      await escrow.connect(agentAOwner).cancelTask(taskId);
      const after = await ethers.provider.getBalance(agentAOwner.address);
      expect(after).to.be.gt(before - ethers.parseEther("0.001"));
    });

    it("payer can dispute within verify window", async function () {
      await escrow.connect(agentBOwner).acceptTask(taskId, agentBId);
      await escrow.connect(agentBOwner).submitResult(taskId, "bad result");
      await escrow.connect(agentAOwner).disputeTask(taskId);
      expect((await escrow.getTask(taskId)).status).to.equal(4n);
    });
  });
});
