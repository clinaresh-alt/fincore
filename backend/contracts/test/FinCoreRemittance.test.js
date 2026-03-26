const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time, loadFixture } = require("@nomicfoundation/hardhat-toolbox/network-helpers");

/**
 * Tests unitarios para FinCoreRemittance.sol
 * Contrato de escrow para remesas transfronterizas con time-lock de 48h
 */
describe("FinCoreRemittance", function () {
  // Constantes del contrato
  const TIMELOCK_DURATION = 48 * 60 * 60; // 48 horas en segundos
  const MIN_AMOUNT = ethers.parseUnits("1", 6); // 1 USDC
  const MAX_AMOUNT = ethers.parseUnits("100000", 6); // 100,000 USDC
  const PLATFORM_FEE_BPS = 150; // 1.5%

  // Roles
  const DEFAULT_ADMIN_ROLE = ethers.ZeroHash;
  const OPERATOR_ROLE = ethers.keccak256(ethers.toUtf8Bytes("OPERATOR_ROLE"));
  const ADMIN_ROLE = ethers.keccak256(ethers.toUtf8Bytes("ADMIN_ROLE"));

  /**
   * Fixture para deploy del contrato y setup inicial
   */
  async function deployRemittanceFixture() {
    const [owner, operator, liquidityPool, sender1, sender2, unauthorized] = await ethers.getSigners();

    // Deploy Mock USDC (6 decimals)
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    const usdc = await MockERC20.deploy("USD Coin", "USDC", 6);
    await usdc.waitForDeployment();

    // Deploy Mock USDT
    const usdt = await MockERC20.deploy("Tether USD", "USDT", 6);
    await usdt.waitForDeployment();

    // Deploy FinCoreRemittance
    const FinCoreRemittance = await ethers.getContractFactory("FinCoreRemittance");
    const remittance = await FinCoreRemittance.deploy(
      liquidityPool.address,
      PLATFORM_FEE_BPS
    );
    await remittance.waitForDeployment();

    // Add USDC as supported token
    await remittance.addSupportedToken(await usdc.getAddress());

    // Grant OPERATOR_ROLE to operator
    await remittance.grantRole(OPERATOR_ROLE, operator.address);

    // Mint tokens to senders
    const mintAmount = ethers.parseUnits("100000", 6); // 100,000 USDC
    await usdc.mint(sender1.address, mintAmount);
    await usdc.mint(sender2.address, mintAmount);

    // Approve remittance contract
    await usdc.connect(sender1).approve(await remittance.getAddress(), ethers.MaxUint256);
    await usdc.connect(sender2).approve(await remittance.getAddress(), ethers.MaxUint256);

    return {
      remittance,
      usdc,
      usdt,
      owner,
      operator,
      liquidityPool,
      sender1,
      sender2,
      unauthorized
    };
  }

  /**
   * Helper para generar referenceId unico
   */
  function generateReferenceId() {
    return ethers.encodeBytes32String(`REM-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`);
  }

  // ==================== DEPLOYMENT TESTS ====================

  describe("Deployment", function () {
    it("Should set the correct liquidity pool", async function () {
      const { remittance, liquidityPool } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.liquidityPool()).to.equal(liquidityPool.address);
    });

    it("Should set the correct platform fee", async function () {
      const { remittance } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.platformFeeBps()).to.equal(PLATFORM_FEE_BPS);
    });

    it("Should grant DEFAULT_ADMIN_ROLE to deployer", async function () {
      const { remittance, owner } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.true;
    });

    it("Should grant ADMIN_ROLE to deployer", async function () {
      const { remittance, owner } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.hasRole(ADMIN_ROLE, owner.address)).to.be.true;
    });

    it("Should grant OPERATOR_ROLE to deployer", async function () {
      const { remittance, owner } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.hasRole(OPERATOR_ROLE, owner.address)).to.be.true;
    });

    it("Should revert if liquidity pool is zero address", async function () {
      const FinCoreRemittance = await ethers.getContractFactory("FinCoreRemittance");
      await expect(
        FinCoreRemittance.deploy(ethers.ZeroAddress, PLATFORM_FEE_BPS)
      ).to.be.revertedWithCustomError(FinCoreRemittance, "InvalidAddress");
    });

    it("Should have correct TIMELOCK_DURATION constant", async function () {
      const { remittance } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.TIMELOCK_DURATION()).to.equal(TIMELOCK_DURATION);
    });

    it("Should have correct MIN_AMOUNT constant", async function () {
      const { remittance } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.MIN_AMOUNT()).to.equal(MIN_AMOUNT);
    });

    it("Should have correct MAX_AMOUNT constant", async function () {
      const { remittance } = await loadFixture(deployRemittanceFixture);
      expect(await remittance.MAX_AMOUNT()).to.equal(MAX_AMOUNT);
    });

    it("Should initialize with zero totals", async function () {
      const { remittance } = await loadFixture(deployRemittanceFixture);
      const [locked, released, refunded, fees] = await remittance.getTotals();
      expect(locked).to.equal(0);
      expect(released).to.equal(0);
      expect(refunded).to.equal(0);
      expect(fees).to.equal(0);
    });
  });

  // ==================== LOCK FUNDS TESTS ====================

  describe("lockFunds", function () {
    it("Should lock funds successfully", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6); // 1,000 USDC

      await expect(
        remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount)
      ).to.emit(remittance, "RemittanceCreated");
    });

    it("Should store correct remittance data", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      const remittanceData = await remittance.getRemittance(1);
      expect(remittanceData.referenceId).to.equal(referenceId);
      expect(remittanceData.sender).to.equal(sender1.address);
      expect(remittanceData.token).to.equal(await usdc.getAddress());
      expect(remittanceData.state).to.equal(0); // Locked
    });

    it("Should calculate platform fee correctly (1.5%)", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);
      const expectedFee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const expectedNetAmount = amount - expectedFee;

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      const remittanceData = await remittance.getRemittance(1);
      expect(remittanceData.amount).to.equal(expectedNetAmount);
      expect(remittanceData.platformFee).to.equal(expectedFee);
    });

    it("Should transfer fee to liquidity pool", async function () {
      const { remittance, usdc, sender1, liquidityPool } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);
      const expectedFee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);

      const poolBalanceBefore = await usdc.balanceOf(liquidityPool.address);
      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);
      const poolBalanceAfter = await usdc.balanceOf(liquidityPool.address);

      expect(poolBalanceAfter - poolBalanceBefore).to.equal(expectedFee);
    });

    it("Should set correct expiration time (48 hours)", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);

      const tx = await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);
      const block = await ethers.provider.getBlock(tx.blockNumber);

      const remittanceData = await remittance.getRemittance(1);
      expect(remittanceData.expiresAt).to.equal(BigInt(block.timestamp) + BigInt(TIMELOCK_DURATION));
    });

    it("Should update totalLocked", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);
      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      const [locked] = await remittance.getTotals();
      expect(locked).to.equal(netAmount);
    });

    it("Should increment nextRemittanceId", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);

      expect(await remittance.nextRemittanceId()).to.equal(0);

      await remittance.connect(sender1).lockFunds(
        generateReferenceId(),
        await usdc.getAddress(),
        ethers.parseUnits("100", 6)
      );
      expect(await remittance.nextRemittanceId()).to.equal(1);

      await remittance.connect(sender1).lockFunds(
        generateReferenceId(),
        await usdc.getAddress(),
        ethers.parseUnits("100", 6)
      );
      expect(await remittance.nextRemittanceId()).to.equal(2);
    });

    it("Should revert if amount is below minimum", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("0.5", 6); // 0.5 USDC < 1 USDC min

      await expect(
        remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount)
      ).to.be.revertedWithCustomError(remittance, "InvalidAmount");
    });

    it("Should revert if amount exceeds maximum", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("150000", 6); // 150,000 USDC > 100,000 max

      // Mint extra tokens for this test
      await usdc.mint(sender1.address, amount);

      await expect(
        remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount)
      ).to.be.revertedWithCustomError(remittance, "InvalidAmount");
    });

    it("Should revert if token is not supported", async function () {
      const { remittance, usdt, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("100", 6);

      // USDT not added to supported tokens in fixture
      await expect(
        remittance.connect(sender1).lockFunds(referenceId, await usdt.getAddress(), amount)
      ).to.be.revertedWithCustomError(remittance, "TokenNotSupported");
    });

    it("Should revert if referenceId already used", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("100", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      await expect(
        remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount)
      ).to.be.revertedWithCustomError(remittance, "ReferenceAlreadyUsed");
    });

    it("Should revert when contract is paused", async function () {
      const { remittance, usdc, sender1, owner } = await loadFixture(deployRemittanceFixture);

      await remittance.connect(owner).pause();

      await expect(
        remittance.connect(sender1).lockFunds(generateReferenceId(), await usdc.getAddress(), ethers.parseUnits("100", 6))
      ).to.be.revertedWithCustomError(remittance, "EnforcedPause");
    });

    it("Should map referenceId to remittanceId", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);
      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("100", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      expect(await remittance.getRemittanceByReference(referenceId)).to.equal(1);
    });
  });

  // ==================== RELEASE FUNDS TESTS ====================

  describe("releaseFunds", function () {
    async function lockFundsFixture() {
      const fixture = await loadFixture(deployRemittanceFixture);
      const { remittance, usdc, sender1 } = fixture;

      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      return { ...fixture, referenceId, amount };
    }

    it("Should release funds successfully", async function () {
      const { remittance, operator } = await loadFixture(lockFundsFixture);

      await expect(
        remittance.connect(operator).releaseFunds(1)
      ).to.emit(remittance, "RemittanceReleased");
    });

    it("Should transfer funds to liquidity pool", async function () {
      const { remittance, usdc, operator, liquidityPool, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      const poolBalanceBefore = await usdc.balanceOf(liquidityPool.address);
      await remittance.connect(operator).releaseFunds(1);
      const poolBalanceAfter = await usdc.balanceOf(liquidityPool.address);

      expect(poolBalanceAfter - poolBalanceBefore).to.equal(netAmount);
    });

    it("Should update remittance state to Released", async function () {
      const { remittance, operator } = await loadFixture(lockFundsFixture);

      await remittance.connect(operator).releaseFunds(1);

      const remittanceData = await remittance.getRemittance(1);
      expect(remittanceData.state).to.equal(1); // Released
    });

    it("Should update totalLocked and totalReleased", async function () {
      const { remittance, operator, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      await remittance.connect(operator).releaseFunds(1);

      const [locked, released] = await remittance.getTotals();
      expect(locked).to.equal(0);
      expect(released).to.equal(netAmount);
    });

    it("Should only allow OPERATOR_ROLE to release", async function () {
      const { remittance, unauthorized } = await loadFixture(lockFundsFixture);

      await expect(
        remittance.connect(unauthorized).releaseFunds(1)
      ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
    });

    it("Should revert if remittance not found", async function () {
      const { remittance, operator } = await loadFixture(lockFundsFixture);

      await expect(
        remittance.connect(operator).releaseFunds(999)
      ).to.be.revertedWithCustomError(remittance, "RemittanceNotFound");
    });

    it("Should revert if already released", async function () {
      const { remittance, operator } = await loadFixture(lockFundsFixture);

      await remittance.connect(operator).releaseFunds(1);

      await expect(
        remittance.connect(operator).releaseFunds(1)
      ).to.be.revertedWithCustomError(remittance, "InvalidState");
    });

    it("Should revert when contract is paused", async function () {
      const { remittance, owner, operator } = await loadFixture(lockFundsFixture);

      await remittance.connect(owner).pause();

      await expect(
        remittance.connect(operator).releaseFunds(1)
      ).to.be.revertedWithCustomError(remittance, "EnforcedPause");
    });
  });

  // ==================== REFUND TESTS (48h TIME-LOCK) ====================

  describe("refund (48h time-lock)", function () {
    async function lockFundsFixture() {
      const fixture = await loadFixture(deployRemittanceFixture);
      const { remittance, usdc, sender1 } = fixture;

      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      return { ...fixture, referenceId, amount };
    }

    it("Should refund after 48 hours", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      // Advance time by 48 hours + 1 second
      await time.increase(TIMELOCK_DURATION + 1);

      await expect(
        remittance.connect(sender1).refund(1)
      ).to.emit(remittance, "RemittanceRefunded");
    });

    it("Should return funds to sender", async function () {
      const { remittance, usdc, sender1, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      const senderBalanceBefore = await usdc.balanceOf(sender1.address);

      await time.increase(TIMELOCK_DURATION + 1);
      await remittance.connect(sender1).refund(1);

      const senderBalanceAfter = await usdc.balanceOf(sender1.address);
      expect(senderBalanceAfter - senderBalanceBefore).to.equal(netAmount);
    });

    it("Should update remittance state to Refunded", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      await time.increase(TIMELOCK_DURATION + 1);
      await remittance.connect(sender1).refund(1);

      const remittanceData = await remittance.getRemittance(1);
      expect(remittanceData.state).to.equal(2); // Refunded
    });

    it("Should update totalLocked and totalRefunded", async function () {
      const { remittance, sender1, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      await time.increase(TIMELOCK_DURATION + 1);
      await remittance.connect(sender1).refund(1);

      const [locked, , refunded] = await remittance.getTotals();
      expect(locked).to.equal(0);
      expect(refunded).to.equal(netAmount);
    });

    it("Should revert if not expired (before 48h)", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      // Only advance 24 hours
      await time.increase(24 * 60 * 60);

      await expect(
        remittance.connect(sender1).refund(1)
      ).to.be.revertedWithCustomError(remittance, "NotExpired");
    });

    it("Should revert at 47 hours (before 48h expiration)", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      // Advance 47 hours (1 hour before expiration)
      await time.increase(47 * 60 * 60);

      await expect(
        remittance.connect(sender1).refund(1)
      ).to.be.revertedWithCustomError(remittance, "NotExpired");
    });

    it("Should allow anyone to call refund after expiration", async function () {
      const { remittance, usdc, sender1, unauthorized, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      const senderBalanceBefore = await usdc.balanceOf(sender1.address);

      await time.increase(TIMELOCK_DURATION + 1);
      // Called by unauthorized user, but funds go to original sender
      await remittance.connect(unauthorized).refund(1);

      const senderBalanceAfter = await usdc.balanceOf(sender1.address);
      expect(senderBalanceAfter - senderBalanceBefore).to.equal(netAmount);
    });

    it("Should revert if remittance not found", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      await time.increase(TIMELOCK_DURATION + 1);

      await expect(
        remittance.connect(sender1).refund(999)
      ).to.be.revertedWithCustomError(remittance, "RemittanceNotFound");
    });

    it("Should revert if already refunded", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      await time.increase(TIMELOCK_DURATION + 1);
      await remittance.connect(sender1).refund(1);

      await expect(
        remittance.connect(sender1).refund(1)
      ).to.be.revertedWithCustomError(remittance, "InvalidState");
    });

    it("Should revert when contract is paused", async function () {
      const { remittance, owner, sender1 } = await loadFixture(lockFundsFixture);

      await time.increase(TIMELOCK_DURATION + 1);
      await remittance.connect(owner).pause();

      await expect(
        remittance.connect(sender1).refund(1)
      ).to.be.revertedWithCustomError(remittance, "EnforcedPause");
    });

    it("canRefund should return false before 48h", async function () {
      const { remittance } = await loadFixture(lockFundsFixture);

      expect(await remittance.canRefund(1)).to.be.false;
    });

    it("canRefund should return true after 48h", async function () {
      const { remittance } = await loadFixture(lockFundsFixture);

      await time.increase(TIMELOCK_DURATION + 1);
      expect(await remittance.canRefund(1)).to.be.true;
    });
  });

  // ==================== CANCEL BY SENDER TESTS ====================

  describe("cancelBySender", function () {
    async function lockFundsFixture() {
      const fixture = await loadFixture(deployRemittanceFixture);
      const { remittance, usdc, sender1 } = fixture;

      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      return { ...fixture, referenceId, amount };
    }

    it("Should allow sender to cancel", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      await expect(
        remittance.connect(sender1).cancelBySender(1)
      ).to.emit(remittance, "RemittanceRefunded");
    });

    it("Should return funds to sender", async function () {
      const { remittance, usdc, sender1, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      const senderBalanceBefore = await usdc.balanceOf(sender1.address);
      await remittance.connect(sender1).cancelBySender(1);
      const senderBalanceAfter = await usdc.balanceOf(sender1.address);

      expect(senderBalanceAfter - senderBalanceBefore).to.equal(netAmount);
    });

    it("Should update remittance state to Cancelled", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      await remittance.connect(sender1).cancelBySender(1);

      const remittanceData = await remittance.getRemittance(1);
      expect(remittanceData.state).to.equal(3); // Cancelled
    });

    it("Should revert if caller is not sender", async function () {
      const { remittance, sender2 } = await loadFixture(lockFundsFixture);

      await expect(
        remittance.connect(sender2).cancelBySender(1)
      ).to.be.revertedWithCustomError(remittance, "NotSender");
    });

    it("Should revert if remittance not found", async function () {
      const { remittance, sender1 } = await loadFixture(lockFundsFixture);

      await expect(
        remittance.connect(sender1).cancelBySender(999)
      ).to.be.revertedWithCustomError(remittance, "RemittanceNotFound");
    });

    it("Should revert if already released", async function () {
      const { remittance, sender1, operator } = await loadFixture(lockFundsFixture);

      await remittance.connect(operator).releaseFunds(1);

      await expect(
        remittance.connect(sender1).cancelBySender(1)
      ).to.be.revertedWithCustomError(remittance, "InvalidState");
    });

    it("Should revert when contract is paused", async function () {
      const { remittance, owner, sender1 } = await loadFixture(lockFundsFixture);

      await remittance.connect(owner).pause();

      await expect(
        remittance.connect(sender1).cancelBySender(1)
      ).to.be.revertedWithCustomError(remittance, "EnforcedPause");
    });
  });

  // ==================== ADMIN FUNCTIONS TESTS ====================

  describe("Admin functions", function () {
    describe("addSupportedToken", function () {
      it("Should add supported token", async function () {
        const { remittance, usdt, owner } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(owner).addSupportedToken(await usdt.getAddress())
        ).to.emit(remittance, "TokenAdded");

        expect(await remittance.supportedTokens(await usdt.getAddress())).to.be.true;
      });

      it("Should only allow ADMIN_ROLE", async function () {
        const { remittance, usdt, unauthorized } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(unauthorized).addSupportedToken(await usdt.getAddress())
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });

      it("Should revert for zero address", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(owner).addSupportedToken(ethers.ZeroAddress)
        ).to.be.revertedWithCustomError(remittance, "InvalidAddress");
      });
    });

    describe("removeSupportedToken", function () {
      it("Should remove supported token", async function () {
        const { remittance, usdc, owner } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(owner).removeSupportedToken(await usdc.getAddress())
        ).to.emit(remittance, "TokenRemoved");

        expect(await remittance.supportedTokens(await usdc.getAddress())).to.be.false;
      });

      it("Should only allow ADMIN_ROLE", async function () {
        const { remittance, usdc, unauthorized } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(unauthorized).removeSupportedToken(await usdc.getAddress())
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });
    });

    describe("setLiquidityPool", function () {
      it("Should update liquidity pool", async function () {
        const { remittance, owner, sender1 } = await loadFixture(deployRemittanceFixture);
        const newPool = sender1.address;

        await expect(
          remittance.connect(owner).setLiquidityPool(newPool)
        ).to.emit(remittance, "LiquidityPoolUpdated");

        expect(await remittance.liquidityPool()).to.equal(newPool);
      });

      it("Should only allow ADMIN_ROLE", async function () {
        const { remittance, unauthorized, sender1 } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(unauthorized).setLiquidityPool(sender1.address)
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });

      it("Should revert for zero address", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(owner).setLiquidityPool(ethers.ZeroAddress)
        ).to.be.revertedWithCustomError(remittance, "InvalidAddress");
      });
    });

    describe("setPlatformFee", function () {
      it("Should update platform fee", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);
        const newFee = 200; // 2%

        await expect(
          remittance.connect(owner).setPlatformFee(newFee)
        ).to.emit(remittance, "PlatformFeeUpdated");

        expect(await remittance.platformFeeBps()).to.equal(newFee);
      });

      it("Should only allow ADMIN_ROLE", async function () {
        const { remittance, unauthorized } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(unauthorized).setPlatformFee(200)
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });

      it("Should revert if fee exceeds 5%", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(owner).setPlatformFee(501) // 5.01%
        ).to.be.revertedWith("Fee too high");
      });

      it("Should allow exactly 5%", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);

        await remittance.connect(owner).setPlatformFee(500);
        expect(await remittance.platformFeeBps()).to.equal(500);
      });
    });

    describe("pause/unpause", function () {
      it("Should pause contract", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);

        await remittance.connect(owner).pause();
        expect(await remittance.paused()).to.be.true;
      });

      it("Should unpause contract", async function () {
        const { remittance, owner } = await loadFixture(deployRemittanceFixture);

        await remittance.connect(owner).pause();
        await remittance.connect(owner).unpause();
        expect(await remittance.paused()).to.be.false;
      });

      it("Should only allow ADMIN_ROLE to pause", async function () {
        const { remittance, unauthorized } = await loadFixture(deployRemittanceFixture);

        await expect(
          remittance.connect(unauthorized).pause()
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });

      it("Should only allow ADMIN_ROLE to unpause", async function () {
        const { remittance, owner, unauthorized } = await loadFixture(deployRemittanceFixture);

        await remittance.connect(owner).pause();

        await expect(
          remittance.connect(unauthorized).unpause()
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });
    });

    describe("rescueTokens", function () {
      it("Should rescue accidentally sent tokens", async function () {
        const { remittance, usdt, owner, sender1 } = await loadFixture(deployRemittanceFixture);

        // Mint USDT directly to contract (simulating accidental transfer)
        const rescueAmount = ethers.parseUnits("100", 6);
        await usdt.mint(await remittance.getAddress(), rescueAmount);

        const ownerBalanceBefore = await usdt.balanceOf(owner.address);
        await remittance.connect(owner).rescueTokens(await usdt.getAddress(), owner.address, rescueAmount);
        const ownerBalanceAfter = await usdt.balanceOf(owner.address);

        expect(ownerBalanceAfter - ownerBalanceBefore).to.equal(rescueAmount);
      });

      it("Should not allow rescuing locked funds", async function () {
        const { remittance, usdc, owner, sender1 } = await loadFixture(deployRemittanceFixture);

        // Lock some funds
        const lockAmount = ethers.parseUnits("1000", 6);
        await remittance.connect(sender1).lockFunds(
          generateReferenceId(),
          await usdc.getAddress(),
          lockAmount
        );

        const fee = lockAmount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
        const lockedAmount = lockAmount - fee;

        // Try to rescue more than available (locked funds)
        await expect(
          remittance.connect(owner).rescueTokens(await usdc.getAddress(), owner.address, lockedAmount)
        ).to.be.revertedWith("Cannot withdraw locked funds");
      });

      it("Should only allow ADMIN_ROLE", async function () {
        const { remittance, usdt, unauthorized, owner } = await loadFixture(deployRemittanceFixture);

        await usdt.mint(await remittance.getAddress(), ethers.parseUnits("100", 6));

        await expect(
          remittance.connect(unauthorized).rescueTokens(await usdt.getAddress(), owner.address, 100)
        ).to.be.revertedWithCustomError(remittance, "AccessControlUnauthorizedAccount");
      });

      it("Should revert for zero address recipient", async function () {
        const { remittance, usdt, owner } = await loadFixture(deployRemittanceFixture);

        await usdt.mint(await remittance.getAddress(), ethers.parseUnits("100", 6));

        await expect(
          remittance.connect(owner).rescueTokens(await usdt.getAddress(), ethers.ZeroAddress, 100)
        ).to.be.revertedWithCustomError(remittance, "InvalidAddress");
      });
    });
  });

  // ==================== VIEW FUNCTIONS TESTS ====================

  describe("View functions", function () {
    async function lockFundsFixture() {
      const fixture = await loadFixture(deployRemittanceFixture);
      const { remittance, usdc, sender1 } = fixture;

      const referenceId = generateReferenceId();
      const amount = ethers.parseUnits("1000", 6);

      await remittance.connect(sender1).lockFunds(referenceId, await usdc.getAddress(), amount);

      return { ...fixture, referenceId, amount };
    }

    it("getRemittance should return correct data", async function () {
      const { remittance, usdc, sender1, referenceId, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      const data = await remittance.getRemittance(1);

      expect(data.referenceId).to.equal(referenceId);
      expect(data.sender).to.equal(sender1.address);
      expect(data.token).to.equal(await usdc.getAddress());
      expect(data.amount).to.equal(netAmount);
      expect(data.platformFee).to.equal(fee);
      expect(data.state).to.equal(0); // Locked
    });

    it("getRemittanceByReference should return correct id", async function () {
      const { remittance, referenceId } = await loadFixture(lockFundsFixture);

      expect(await remittance.getRemittanceByReference(referenceId)).to.equal(1);
    });

    it("getTotals should return correct values", async function () {
      const { remittance, usdc, sender1, operator, amount } = await loadFixture(lockFundsFixture);

      const fee = amount * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const netAmount = amount - fee;

      // Check after lock
      let [locked, released, refunded, fees] = await remittance.getTotals();
      expect(locked).to.equal(netAmount);
      expect(released).to.equal(0);
      expect(refunded).to.equal(0);
      expect(fees).to.equal(fee);

      // Release funds
      await remittance.connect(operator).releaseFunds(1);

      // Check after release
      [locked, released, refunded, fees] = await remittance.getTotals();
      expect(locked).to.equal(0);
      expect(released).to.equal(netAmount);
      expect(refunded).to.equal(0);
    });
  });

  // ==================== MULTIPLE REMITTANCES TESTS ====================

  describe("Multiple remittances", function () {
    it("Should handle multiple concurrent remittances", async function () {
      const { remittance, usdc, sender1, sender2, operator } = await loadFixture(deployRemittanceFixture);

      const amount1 = ethers.parseUnits("500", 6);
      const amount2 = ethers.parseUnits("750", 6);
      const amount3 = ethers.parseUnits("1000", 6);

      // Create 3 remittances
      await remittance.connect(sender1).lockFunds(generateReferenceId(), await usdc.getAddress(), amount1);
      await remittance.connect(sender2).lockFunds(generateReferenceId(), await usdc.getAddress(), amount2);
      await remittance.connect(sender1).lockFunds(generateReferenceId(), await usdc.getAddress(), amount3);

      expect(await remittance.nextRemittanceId()).to.equal(3);

      // Release first, refund second (after time), cancel third
      await remittance.connect(operator).releaseFunds(1);

      await time.increase(TIMELOCK_DURATION + 1);
      await remittance.connect(sender2).refund(2);

      // Third remittance is still locked, sender can cancel
      // Note: After time increase, third is also expired, so we use a different approach
      // Let's check states
      const rem1 = await remittance.getRemittance(1);
      const rem2 = await remittance.getRemittance(2);

      expect(rem1.state).to.equal(1); // Released
      expect(rem2.state).to.equal(2); // Refunded
    });

    it("Should track totals correctly across multiple remittances", async function () {
      const { remittance, usdc, sender1, sender2, operator } = await loadFixture(deployRemittanceFixture);

      const amount1 = ethers.parseUnits("1000", 6);
      const amount2 = ethers.parseUnits("2000", 6);

      const fee1 = amount1 * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const fee2 = amount2 * BigInt(PLATFORM_FEE_BPS) / BigInt(10000);
      const net1 = amount1 - fee1;
      const net2 = amount2 - fee2;

      await remittance.connect(sender1).lockFunds(generateReferenceId(), await usdc.getAddress(), amount1);
      await remittance.connect(sender2).lockFunds(generateReferenceId(), await usdc.getAddress(), amount2);

      let [locked, , , fees] = await remittance.getTotals();
      expect(locked).to.equal(net1 + net2);
      expect(fees).to.equal(fee1 + fee2);

      // Release first
      await remittance.connect(operator).releaseFunds(1);

      [locked, released, , ] = await remittance.getTotals();
      expect(locked).to.equal(net2);
      expect(released).to.equal(net1);
    });
  });

  // ==================== EDGE CASES ====================

  describe("Edge cases", function () {
    it("Should handle minimum amount correctly", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);

      // Exactly minimum amount should work
      await expect(
        remittance.connect(sender1).lockFunds(
          generateReferenceId(),
          await usdc.getAddress(),
          MIN_AMOUNT
        )
      ).to.not.be.reverted;
    });

    it("Should handle maximum amount correctly", async function () {
      const { remittance, usdc, sender1 } = await loadFixture(deployRemittanceFixture);

      // Mint more tokens
      await usdc.mint(sender1.address, MAX_AMOUNT);

      // Exactly maximum amount should work
      await expect(
        remittance.connect(sender1).lockFunds(
          generateReferenceId(),
          await usdc.getAddress(),
          MAX_AMOUNT
        )
      ).to.not.be.reverted;
    });

    it("Should handle zero fee scenario", async function () {
      const { remittance, usdc, sender1, owner } = await loadFixture(deployRemittanceFixture);

      // Set fee to 0
      await remittance.connect(owner).setPlatformFee(0);

      const amount = ethers.parseUnits("1000", 6);
      await remittance.connect(sender1).lockFunds(generateReferenceId(), await usdc.getAddress(), amount);

      const data = await remittance.getRemittance(1);
      expect(data.amount).to.equal(amount);
      expect(data.platformFee).to.equal(0);
    });
  });
});
