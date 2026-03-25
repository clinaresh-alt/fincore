/**
 * FinCore - Script de Deployment de Infraestructura
 *
 * Despliega los contratos base del sistema:
 * 1. FinCoreKYC - Sistema de verificacion KYC on-chain
 * 2. FinCoreInvestment - Contrato de inversiones con escrow
 * 3. FinCoreDividends - Sistema de distribucion de dividendos
 *
 * Uso: npx hardhat run scripts/deploy.js --network <network>
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

// Direcciones USDC por red
const USDC_ADDRESSES = {
  polygon: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",     // USDC nativo
  polygonAmoy: "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582",  // USDC testnet
  sepolia: "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",      // USDC testnet
  arbitrum: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",     // USDC nativo
  base: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",         // USDC nativo
  hardhat: "0x0000000000000000000000000000000000000001",      // Placeholder
  localhost: "0x0000000000000000000000000000000000000001"     // Placeholder
};

// Configuracion de deployment
const DEPLOYMENT_CONFIG = {
  // KYC Config
  kycValidityPeriodDays: 365,

  // Investment Config
  paymentTokenDecimals: 6, // USDC tiene 6 decimales

  // Dividends Config
  claimExpirationDays: 90
};

async function main() {
  console.log("\n");
  console.log("=".repeat(60));
  console.log("        FINCORE - SMART CONTRACTS DEPLOYMENT");
  console.log("=".repeat(60));
  console.log("\n");

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

  // Verificar balance minimo
  if (balance < hre.ethers.parseEther("0.01")) {
    throw new Error("Balance insuficiente para deployment");
  }

  // Obtener direccion de USDC
  const usdcAddress = USDC_ADDRESSES[network];
  if (!usdcAddress) {
    throw new Error(`Red no soportada: ${network}. Redes disponibles: ${Object.keys(USDC_ADDRESSES).join(", ")}`);
  }
  console.log("USDC Address:", usdcAddress);
  console.log("\n");

  // Objeto para almacenar direcciones desplegadas
  const deployedAddresses = {
    network,
    chainId,
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
    contracts: {}
  };

  // ========== 1. DEPLOY FINCORE KYC ==========
  console.log("-".repeat(60));
  console.log("1. Desplegando FinCoreKYC...");
  console.log("-".repeat(60));

  const FinCoreKYC = await hre.ethers.getContractFactory("FinCoreKYC");
  const kycContract = await FinCoreKYC.deploy(
    deployer.address,
    DEPLOYMENT_CONFIG.kycValidityPeriodDays
  );
  await kycContract.waitForDeployment();
  const kycAddress = await kycContract.getAddress();

  console.log("   FinCoreKYC desplegado en:", kycAddress);
  console.log("   Periodo de validez:", DEPLOYMENT_CONFIG.kycValidityPeriodDays, "dias");

  deployedAddresses.contracts.FinCoreKYC = {
    address: kycAddress,
    constructorArgs: [deployer.address, DEPLOYMENT_CONFIG.kycValidityPeriodDays]
  };

  // ========== 2. DEPLOY FINCORE INVESTMENT ==========
  console.log("\n");
  console.log("-".repeat(60));
  console.log("2. Desplegando FinCoreInvestment...");
  console.log("-".repeat(60));

  const FinCoreInvestment = await hre.ethers.getContractFactory("FinCoreInvestment");
  const investmentContract = await FinCoreInvestment.deploy(
    usdcAddress,
    DEPLOYMENT_CONFIG.paymentTokenDecimals,
    deployer.address, // feeRecipient
    deployer.address  // admin
  );
  await investmentContract.waitForDeployment();
  const investmentAddress = await investmentContract.getAddress();

  console.log("   FinCoreInvestment desplegado en:", investmentAddress);
  console.log("   Payment Token (USDC):", usdcAddress);
  console.log("   Fee Recipient:", deployer.address);

  deployedAddresses.contracts.FinCoreInvestment = {
    address: investmentAddress,
    constructorArgs: [
      usdcAddress,
      DEPLOYMENT_CONFIG.paymentTokenDecimals,
      deployer.address,
      deployer.address
    ]
  };

  // ========== 3. DEPLOY FINCORE DIVIDENDS ==========
  console.log("\n");
  console.log("-".repeat(60));
  console.log("3. Desplegando FinCoreDividends...");
  console.log("-".repeat(60));

  const FinCoreDividends = await hre.ethers.getContractFactory("FinCoreDividends");
  const dividendsContract = await FinCoreDividends.deploy(
    usdcAddress,
    DEPLOYMENT_CONFIG.claimExpirationDays,
    deployer.address
  );
  await dividendsContract.waitForDeployment();
  const dividendsAddress = await dividendsContract.getAddress();

  console.log("   FinCoreDividends desplegado en:", dividendsAddress);
  console.log("   Periodo de reclamo:", DEPLOYMENT_CONFIG.claimExpirationDays, "dias");

  deployedAddresses.contracts.FinCoreDividends = {
    address: dividendsAddress,
    constructorArgs: [
      usdcAddress,
      DEPLOYMENT_CONFIG.claimExpirationDays,
      deployer.address
    ]
  };

  // ========== GUARDAR DIRECCIONES ==========
  console.log("\n");
  console.log("=".repeat(60));
  console.log("                    DEPLOYMENT COMPLETADO");
  console.log("=".repeat(60));
  console.log("\n");

  // Guardar a archivo
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const filename = `${network}-${chainId}.json`;
  const filepath = path.join(deploymentsDir, filename);
  fs.writeFileSync(filepath, JSON.stringify(deployedAddresses, null, 2));

  console.log("Archivo de deployment guardado en:", filepath);
  console.log("\n");

  // Mostrar resumen
  console.log("RESUMEN DE CONTRATOS DESPLEGADOS:");
  console.log("-".repeat(60));
  console.log("| Contrato           | Direccion                                  |");
  console.log("-".repeat(60));
  console.log(`| FinCoreKYC         | ${kycAddress} |`);
  console.log(`| FinCoreInvestment  | ${investmentAddress} |`);
  console.log(`| FinCoreDividends   | ${dividendsAddress} |`);
  console.log("-".repeat(60));
  console.log("\n");

  // Instrucciones de verificacion
  console.log("VERIFICACION DE CONTRATOS:");
  console.log("-".repeat(60));
  console.log(`npx hardhat verify --network ${network} ${kycAddress} ${deployer.address} ${DEPLOYMENT_CONFIG.kycValidityPeriodDays}`);
  console.log(`npx hardhat verify --network ${network} ${investmentAddress} ${usdcAddress} ${DEPLOYMENT_CONFIG.paymentTokenDecimals} ${deployer.address} ${deployer.address}`);
  console.log(`npx hardhat verify --network ${network} ${dividendsAddress} ${usdcAddress} ${DEPLOYMENT_CONFIG.claimExpirationDays} ${deployer.address}`);
  console.log("\n");

  // Variables de entorno para backend
  console.log("VARIABLES DE ENTORNO PARA BACKEND (.env):");
  console.log("-".repeat(60));
  console.log(`FINCORE_KYC_CONTRACT=${kycAddress}`);
  console.log(`FINCORE_INVESTMENT_CONTRACT=${investmentAddress}`);
  console.log(`FINCORE_DIVIDENDS_CONTRACT=${dividendsAddress}`);
  console.log("\n");

  return deployedAddresses;
}

main()
  .then((result) => {
    console.log("Deployment exitoso!");
    process.exit(0);
  })
  .catch((error) => {
    console.error("Error durante deployment:", error);
    process.exit(1);
  });
