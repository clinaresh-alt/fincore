/**
 * FinCore - Script de Verificacion de Contratos
 *
 * Verifica todos los contratos desplegados en una red especifica.
 * Lee los datos de deployment y ejecuta la verificacion en Etherscan/Polygonscan.
 *
 * Uso: npx hardhat run scripts/verify-contracts.js --network <network>
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function verifyContract(address, constructorArgs, contractName) {
  console.log(`\nVerificando ${contractName} en ${address}...`);

  try {
    await hre.run("verify:verify", {
      address: address,
      constructorArguments: constructorArgs,
    });
    console.log(`  ${contractName} verificado exitosamente!`);
    return true;
  } catch (error) {
    if (error.message.includes("Already Verified")) {
      console.log(`  ${contractName} ya estaba verificado`);
      return true;
    }
    console.error(`  Error verificando ${contractName}:`, error.message);
    return false;
  }
}

async function main() {
  console.log("\n");
  console.log("=".repeat(60));
  console.log("     FINCORE - CONTRACT VERIFICATION");
  console.log("=".repeat(60));
  console.log("\n");

  const network = hre.network.name;
  const chainId = hre.network.config.chainId;

  console.log("Network:", network);
  console.log("Chain ID:", chainId);
  console.log("\n");

  // Buscar archivo de deployment
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const filename = `${network}-${chainId}.json`;
  const filepath = path.join(deploymentsDir, filename);

  if (!fs.existsSync(filepath)) {
    console.error(`No se encontro archivo de deployment: ${filepath}`);
    console.log("\nAsegurate de haber ejecutado el deployment primero:");
    console.log(`  npx hardhat run scripts/deploy.js --network ${network}`);
    process.exit(1);
  }

  const deployment = JSON.parse(fs.readFileSync(filepath, "utf8"));
  console.log("Deployment encontrado de:", deployment.deployedAt);
  console.log("\n");

  // Verificar cada contrato
  const results = {
    success: [],
    failed: []
  };

  console.log("-".repeat(60));
  console.log("Verificando contratos de infraestructura...");
  console.log("-".repeat(60));

  for (const [name, data] of Object.entries(deployment.contracts)) {
    const success = await verifyContract(
      data.address,
      data.constructorArgs,
      name
    );

    if (success) {
      results.success.push(name);
    } else {
      results.failed.push(name);
    }
  }

  // Verificar tokens si existen
  const tokensDir = path.join(deploymentsDir, "tokens");
  if (fs.existsSync(tokensDir)) {
    const tokenFiles = fs.readdirSync(tokensDir).filter(f =>
      f.endsWith(`-${network}-${chainId}.json`)
    );

    if (tokenFiles.length > 0) {
      console.log("\n");
      console.log("-".repeat(60));
      console.log("Verificando tokens de proyectos...");
      console.log("-".repeat(60));

      for (const tokenFile of tokenFiles) {
        const tokenPath = path.join(tokensDir, tokenFile);
        const tokenData = JSON.parse(fs.readFileSync(tokenPath, "utf8"));

        const success = await verifyContract(
          tokenData.token.address,
          tokenData.token.constructorArgs,
          `Token: ${tokenData.token.symbol}`
        );

        if (success) {
          results.success.push(`Token: ${tokenData.token.symbol}`);
        } else {
          results.failed.push(`Token: ${tokenData.token.symbol}`);
        }
      }
    }
  }

  // Resumen
  console.log("\n");
  console.log("=".repeat(60));
  console.log("                RESUMEN DE VERIFICACION");
  console.log("=".repeat(60));
  console.log("\n");

  console.log(`Verificados exitosamente: ${results.success.length}`);
  results.success.forEach(name => console.log(`  - ${name}`));

  if (results.failed.length > 0) {
    console.log(`\nFallidos: ${results.failed.length}`);
    results.failed.forEach(name => console.log(`  - ${name}`));
  }

  console.log("\n");

  // URLs de exploradores
  const explorerUrls = {
    polygon: "https://polygonscan.com",
    polygonAmoy: "https://amoy.polygonscan.com",
    sepolia: "https://sepolia.etherscan.io",
    arbitrum: "https://arbiscan.io",
    base: "https://basescan.org"
  };

  const explorerUrl = explorerUrls[network];
  if (explorerUrl) {
    console.log("Ver contratos verificados en:");
    for (const [name, data] of Object.entries(deployment.contracts)) {
      console.log(`  ${name}: ${explorerUrl}/address/${data.address}#code`);
    }
  }

  console.log("\n");
}

main()
  .then(() => {
    console.log("Verificacion completada!");
    process.exit(0);
  })
  .catch((error) => {
    console.error("Error durante verificacion:", error);
    process.exit(1);
  });
