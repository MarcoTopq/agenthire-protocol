import hre from "hardhat";
import fs from "fs";

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with:", deployer.address);

  const Registry = await hre.ethers.getContractFactory("AgentRegistry");
  const registry = await Registry.deploy();
  await registry.waitForDeployment();
  const registryAddr = await registry.getAddress();
  console.log("AgentRegistry deployed to:", registryAddr);

  const Escrow = await hre.ethers.getContractFactory("TaskEscrow");
  const escrow = await Escrow.deploy(registryAddr, deployer.address);
  await escrow.waitForDeployment();
  const escrowAddr = await escrow.getAddress();
  console.log("TaskEscrow deployed to:", escrowAddr);

  const tx = await registry.setTaskEscrow(escrowAddr);
  await tx.wait();
  console.log("TaskEscrow linked to AgentRegistry ✓");

  const addresses = { registry: registryAddr, escrow: escrowAddr, network: hre.network.name };
  fs.writeFileSync("deployments.json", JSON.stringify(addresses, null, 2));
  console.log("Saved to deployments.json");
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
