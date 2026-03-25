/**
 * FinCore - Script de Deployment de Token de Proyecto
 *
 * Despliega un nuevo FinCoreProjectToken para un proyecto especifico.
 * Este contrato representa la tokenizacion de un proyecto de inversion.
 *
 * Uso: npx hardhat run scripts/deploy-token.js --network <network>
 *
 * Variables de entorno requeridas:
 * - PROJECT_NAME: Nombre del proyecto (ej: "Edificio Centro")
 * - PROJECT_SYMBOL: Simbolo del token (ej: "EDFC")
 * - TOTAL_SUPPLY: Supply total en unidades (ej: 1000000)
 * - PROJECT_URI: URI con metadata del proyecto
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("\n");
  console.log("=".repeat(60));
  console.log("    FINCORE - PROJECT TOKEN DEPLOYMENT");
  console.log("=".repeat(60));
  console.log("\n");

  // Obtener parametros del proyecto
  const projectName = process.env.PROJECT_NAME;
  const projectSymbol = process.env.PROJECT_SYMBOL;
  const totalSupply = process.env.TOTAL_SUPPLY;
  const projectUri = process.env.PROJECT_URI || "";

  // Validar parametros
  if (!projectName || !projectSymbol || !totalSupply) {
    console.error("Error: Faltan parametros requeridos");
    console.log("\nUso:");
    console.log("  PROJECT_NAME='Mi Proyecto' PROJECT_SYMBOL='MPRJ' TOTAL_SUPPLY=1000000 npx hardhat run scripts/deploy-token.js --network polygon");
    console.log("\nParametros:");
    console.log("  PROJECT_NAME  - Nombre completo del proyecto");
    console.log("  PROJECT_SYMBOL - Simbolo del token (3-5 caracteres)");
    console.log("  TOTAL_SUPPLY  - Cantidad total de tokens");
    console.log("  PROJECT_URI   - (Opcional) URI con metadata del proyecto");
    process.exit(1);
  }

  // Validar formato de supply
  const supply = parseInt(totalSupply);
  if (isNaN(supply) || supply <= 0) {
    throw new Error("TOTAL_SUPPLY debe ser un numero positivo");
  }

  // Obtener informacion de la red
  const network = hre.network.name;
  const chainId = hre.network.config.chainId;
  const [deployer] = await hre.ethers.getSigners();
  const balance = await hre.ethers.provider.getBalance(deployer.address);

  console.log("Network:", network);
  console.log("Chain ID:", chainId);
  console.log("Deployer:", deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "ETH/MATIC");
  console.log("\n");

  console.log("Parametros del Token:");
  console.log("-".repeat(60));
  console.log("  Nombre:", projectName);
  console.log("  Simbolo:", projectSymbol);
  console.log("  Supply Total:", supply.toLocaleString());
  console.log("  Project URI:", projectUri || "(ninguno)");
  console.log("\n");

  // Verificar balance minimo
  if (balance < hre.ethers.parseEther("0.005")) {
    throw new Error("Balance insuficiente para deployment");
  }

  // Desplegar token
  console.log("-".repeat(60));
  console.log("Desplegando FinCoreProjectToken...");
  console.log("-".repeat(60));

  const FinCoreProjectToken = await hre.ethers.getContractFactory("FinCoreProjectToken");

  // El constructor de FinCoreProjectToken espera:
  // (string name, string symbol, uint256 totalSupply, string projectUri, address admin)
  const tokenContract = await FinCoreProjectToken.deploy(
    projectName,
    projectSymbol,
    supply,
    projectUri,
    deployer.address
  );

  await tokenContract.waitForDeployment();
  const tokenAddress = await tokenContract.getAddress();

  console.log("\n");
  console.log("=".repeat(60));
  console.log("           TOKEN DESPLEGADO EXITOSAMENTE");
  console.log("=".repeat(60));
  console.log("\n");

  console.log("Direccion del Token:", tokenAddress);
  console.log("\n");

  // Guardar deployment
  const deploymentsDir = path.join(__dirname, "..", "deployments", "tokens");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentData = {
    network,
    chainId,
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
    token: {
      address: tokenAddress,
      name: projectName,
      symbol: projectSymbol,
      totalSupply: supply,
      projectUri,
      constructorArgs: [
        projectName,
        projectSymbol,
        supply,
        projectUri,
        deployer.address
      ]
    }
  };

  const filename = `${projectSymbol.toLowerCase()}-${network}-${chainId}.json`;
  const filepath = path.join(deploymentsDir, filename);
  fs.writeFileSync(filepath, JSON.stringify(deploymentData, null, 2));

  console.log("Deployment guardado en:", filepath);
  console.log("\n");

  // Comando de verificacion
  console.log("VERIFICACION DEL CONTRATO:");
  console.log("-".repeat(60));
  console.log(`npx hardhat verify --network ${network} ${tokenAddress} "${projectName}" "${projectSymbol}" ${supply} "${projectUri}" ${deployer.address}`);
  console.log("\n");

  // Info para integracion
  console.log("INTEGRACION CON FINCORE:");
  console.log("-".repeat(60));
  console.log("Agregar este token al proyecto en la base de datos:");
  console.log(`  token_address: ${tokenAddress}`);
  console.log(`  token_symbol: ${projectSymbol}`);
  console.log(`  total_supply: ${supply}`);
  console.log("\n");

  return deploymentData;
}

main()
  .then((result) => {
    console.log("Deployment de token exitoso!");
    process.exit(0);
  })
  .catch((error) => {
    console.error("Error durante deployment:", error);
    process.exit(1);
  });
