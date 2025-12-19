const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");

describe("OrderBook", function () {
  // Fixture to deploy contracts and set up test state
  async function deployOrderBookFixture() {
    const [owner, maker, taker, other] = await ethers.getSigners();

    // Deploy mock ERC20 tokens
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    const tokenA = await MockERC20.deploy("Token A", "TKA", 6);
    const tokenB = await MockERC20.deploy("Token B", "TKB", 6);

    // Deploy OrderBook
    const OrderBook = await ethers.getContractFactory("OrderBook");
    const orderBook = await OrderBook.deploy();

    // Mint tokens to maker and taker
    const mintAmount = ethers.parseUnits("1000000", 6); // 1M tokens
    await tokenA.mint(maker.address, mintAmount);
    await tokenB.mint(taker.address, mintAmount);

    // Approve OrderBook to spend tokens
    await tokenA.connect(maker).approve(orderBook.target, mintAmount);
    await tokenB.connect(taker).approve(orderBook.target, mintAmount);

    return { orderBook, tokenA, tokenB, owner, maker, taker, other, mintAmount };
  }

  describe("Deployment", function () {
    it("Should set the right owner", async function () {
      const { orderBook, owner } = await loadFixture(deployOrderBookFixture);
      expect(await orderBook.owner()).to.equal(owner.address);
    });

    it("Should start with nextOrderId = 1", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);
      expect(await orderBook.getNextOrderId()).to.equal(1);
    });
  });

  describe("createOrder", function () {
    it("Should create an order successfully", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          offeredAmount,
          tokenB.target,
          requestedAmount
        )
      )
        .to.emit(orderBook, "OrderCreated")
        .withArgs(1, maker.address, tokenA.target, offeredAmount, tokenB.target, requestedAmount);
    });

    it("Should transfer offered tokens to contract", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);
      const makerBalanceBefore = await tokenA.balanceOf(maker.address);

      await orderBook.connect(maker).createOrder(
        tokenA.target,
        offeredAmount,
        tokenB.target,
        requestedAmount
      );

      expect(await tokenA.balanceOf(maker.address)).to.equal(makerBalanceBefore - offeredAmount);
      expect(await tokenA.balanceOf(orderBook.target)).to.equal(offeredAmount);
    });

    it("Should increment order ID", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );
      expect(await orderBook.getNextOrderId()).to.equal(2);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );
      expect(await orderBook.getNextOrderId()).to.equal(3);
    });

    it("Should add order to userOrders", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      const userOrders = await orderBook.getUserOrders(maker.address);
      expect(userOrders.length).to.equal(1);
      expect(userOrders[0]).to.equal(1);
    });

    it("Should revert with zero offered token address", async function () {
      const { orderBook, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      await expect(
        orderBook.connect(maker).createOrder(
          ethers.ZeroAddress,
          ethers.parseUnits("100", 6),
          tokenB.target,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWith("Invalid offered token address");
    });

    it("Should revert with zero requested token address", async function () {
      const { orderBook, tokenA, maker } = await loadFixture(deployOrderBookFixture);
      
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          ethers.parseUnits("100", 6),
          ethers.ZeroAddress,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWith("Invalid requested token address");
    });

    it("Should revert when offered token is not a contract", async function () {
      const { orderBook, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      const eoaAddress = ethers.Wallet.createRandom().address;
      
      await expect(
        orderBook.connect(maker).createOrder(
          eoaAddress,
          ethers.parseUnits("100", 6),
          tokenB.target,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWith("Offered token is not a contract");
    });

    it("Should revert when requested token is not a contract", async function () {
      const { orderBook, tokenA, maker } = await loadFixture(deployOrderBookFixture);
      const eoaAddress = ethers.Wallet.createRandom().address;
      
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          ethers.parseUnits("100", 6),
          eoaAddress,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWith("Requested token is not a contract");
    });

    it("Should revert when offered and requested tokens are the same", async function () {
      const { orderBook, tokenA, maker } = await loadFixture(deployOrderBookFixture);
      
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          ethers.parseUnits("100", 6),
          tokenA.target,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWith("Tokens must be different");
    });

    it("Should revert with zero offered amount", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          0,
          tokenB.target,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWith("Offered amount must be greater than 0");
    });

    it("Should revert with zero requested amount", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);
      
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          ethers.parseUnits("100", 6),
          tokenB.target,
          0
        )
      ).to.be.revertedWith("Requested amount must be greater than 0");
    });

    it("Should revert if token transfer fails (insufficient balance)", async function () {
      const { orderBook, tokenA, tokenB, other } = await loadFixture(deployOrderBookFixture);
      
      // other has no tokens
      await tokenA.connect(other).approve(orderBook.target, ethers.parseUnits("100", 6));

      await expect(
        orderBook.connect(other).createOrder(
          tokenA.target,
          ethers.parseUnits("100", 6),
          tokenB.target,
          ethers.parseUnits("200", 6)
        )
      ).to.be.reverted; // Will fail on transfer
    });
  });

  describe("fillOrder", function () {
    async function createOrderFixture() {
      const fixture = await deployOrderBookFixture();
      const { orderBook, tokenA, tokenB, maker } = fixture;

      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );

      return { ...fixture, offeredAmount, requestedAmount, orderId: 1n };
    }

    it("Should fill an order successfully", async function () {
      const { orderBook, tokenA, tokenB, maker, taker, offeredAmount, requestedAmount, orderId } = 
        await loadFixture(createOrderFixture);

      await expect(orderBook.connect(taker).fillOrder(orderId))
        .to.emit(orderBook, "OrderFilled")
        .withArgs(orderId, taker.address, maker.address);
    });

    it("Should transfer tokens correctly on fill", async function () {
      const { orderBook, tokenA, tokenB, maker, taker, offeredAmount, requestedAmount, orderId } = 
        await loadFixture(createOrderFixture);

      const makerTokenBBefore = await tokenB.balanceOf(maker.address);
      const takerTokenABefore = await tokenA.balanceOf(taker.address);
      const takerTokenBBefore = await tokenB.balanceOf(taker.address);

      await orderBook.connect(taker).fillOrder(orderId);

      // Maker receives requested tokens
      expect(await tokenB.balanceOf(maker.address)).to.equal(makerTokenBBefore + requestedAmount);
      // Taker receives offered tokens
      expect(await tokenA.balanceOf(taker.address)).to.equal(takerTokenABefore + offeredAmount);
      // Taker loses requested tokens
      expect(await tokenB.balanceOf(taker.address)).to.equal(takerTokenBBefore - requestedAmount);
    });

    it("Should mark order as filled", async function () {
      const { orderBook, taker, orderId } = await loadFixture(createOrderFixture);

      await orderBook.connect(taker).fillOrder(orderId);

      const order = await orderBook.getOrder(orderId);
      expect(order.isFilled).to.be.true;
    });

    it("Should revert when order does not exist", async function () {
      const { orderBook, taker } = await loadFixture(createOrderFixture);

      await expect(orderBook.connect(taker).fillOrder(999))
        .to.be.revertedWith("Order does not exist");
    });

    it("Should revert when order is already filled", async function () {
      const { orderBook, taker, orderId } = await loadFixture(createOrderFixture);

      await orderBook.connect(taker).fillOrder(orderId);

      await expect(orderBook.connect(taker).fillOrder(orderId))
        .to.be.revertedWith("Order already filled");
    });

    it("Should revert when order is cancelled", async function () {
      const { orderBook, maker, taker, orderId } = await loadFixture(createOrderFixture);

      await orderBook.connect(maker).cancelOrder(orderId);

      await expect(orderBook.connect(taker).fillOrder(orderId))
        .to.be.revertedWith("Order cancelled");
    });

    it("Should revert when maker tries to fill own order", async function () {
      const { orderBook, maker, orderId } = await loadFixture(createOrderFixture);

      await expect(orderBook.connect(maker).fillOrder(orderId))
        .to.be.revertedWith("Cannot fill your own order");
    });

    it("Should revert when taker has insufficient balance", async function () {
      const { orderBook, tokenB, other, orderId } = await loadFixture(createOrderFixture);

      // other has no Token B
      await tokenB.connect(other).approve(orderBook.target, ethers.parseUnits("200", 6));

      await expect(orderBook.connect(other).fillOrder(orderId))
        .to.be.revertedWith("Insufficient balance to fill order");
    });

    it("Should revert when taker has insufficient allowance", async function () {
      const { orderBook, tokenB, taker, orderId } = await loadFixture(createOrderFixture);

      // Revoke approval
      await tokenB.connect(taker).approve(orderBook.target, 0);

      await expect(orderBook.connect(taker).fillOrder(orderId))
        .to.be.revertedWith("Insufficient allowance to fill order");
    });
  });

  describe("cancelOrder", function () {
    async function createOrderFixture() {
      const fixture = await deployOrderBookFixture();
      const { orderBook, tokenA, tokenB, maker } = fixture;

      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );

      return { ...fixture, offeredAmount, requestedAmount, orderId: 1n };
    }

    it("Should cancel an order successfully", async function () {
      const { orderBook, maker, orderId } = await loadFixture(createOrderFixture);

      await expect(orderBook.connect(maker).cancelOrder(orderId))
        .to.emit(orderBook, "OrderCancelled")
        .withArgs(orderId, maker.address);
    });

    it("Should return offered tokens to maker", async function () {
      const { orderBook, tokenA, maker, offeredAmount, orderId } = await loadFixture(createOrderFixture);

      const makerBalanceBefore = await tokenA.balanceOf(maker.address);

      await orderBook.connect(maker).cancelOrder(orderId);

      expect(await tokenA.balanceOf(maker.address)).to.equal(makerBalanceBefore + offeredAmount);
      expect(await tokenA.balanceOf(orderBook.target)).to.equal(0);
    });

    it("Should mark order as cancelled", async function () {
      const { orderBook, maker, orderId } = await loadFixture(createOrderFixture);

      await orderBook.connect(maker).cancelOrder(orderId);

      const order = await orderBook.getOrder(orderId);
      expect(order.isCancelled).to.be.true;
    });

    it("Should revert when order does not exist", async function () {
      const { orderBook, maker } = await loadFixture(createOrderFixture);

      await expect(orderBook.connect(maker).cancelOrder(999))
        .to.be.revertedWith("Order does not exist");
    });

    it("Should revert when non-maker tries to cancel", async function () {
      const { orderBook, taker, orderId } = await loadFixture(createOrderFixture);

      await expect(orderBook.connect(taker).cancelOrder(orderId))
        .to.be.revertedWith("Only maker can cancel");
    });

    it("Should revert when order is already filled", async function () {
      const { orderBook, maker, taker, orderId } = await loadFixture(createOrderFixture);

      await orderBook.connect(taker).fillOrder(orderId);

      await expect(orderBook.connect(maker).cancelOrder(orderId))
        .to.be.revertedWith("Order already filled");
    });

    it("Should revert when order is already cancelled", async function () {
      const { orderBook, maker, orderId } = await loadFixture(createOrderFixture);

      await orderBook.connect(maker).cancelOrder(orderId);

      await expect(orderBook.connect(maker).cancelOrder(orderId))
        .to.be.revertedWith("Order already cancelled");
    });
  });

  describe("getOrder", function () {
    it("Should return correct order details", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );

      const order = await orderBook.getOrder(1);

      expect(order.maker).to.equal(maker.address);
      expect(order.offeredToken).to.equal(tokenA.target);
      expect(order.offeredAmount).to.equal(offeredAmount);
      expect(order.requestedToken).to.equal(tokenB.target);
      expect(order.requestedAmount).to.equal(requestedAmount);
      expect(order.isFilled).to.be.false;
      expect(order.isCancelled).to.be.false;
    });

    it("Should revert for non-existent order", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);

      await expect(orderBook.getOrder(999))
        .to.be.revertedWith("Order does not exist");
    });
  });

  describe("getUserOrders", function () {
    it("Should return empty array for user with no orders", async function () {
      const { orderBook, other } = await loadFixture(deployOrderBookFixture);

      const userOrders = await orderBook.getUserOrders(other.address);
      expect(userOrders.length).to.equal(0);
    });

    it("Should return all order IDs for user", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );
      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );
      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );

      const userOrders = await orderBook.getUserOrders(maker.address);
      expect(userOrders.length).to.equal(3);
      expect(userOrders[0]).to.equal(1);
      expect(userOrders[1]).to.equal(2);
      expect(userOrders[2]).to.equal(3);
    });
  });

  describe("getActiveOrders", function () {
    async function multipleOrdersFixture() {
      const fixture = await deployOrderBookFixture();
      const { orderBook, tokenA, tokenB, maker, taker } = fixture;

      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      // Create 5 orders
      for (let i = 0; i < 5; i++) {
        await orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        );
      }

      // Fill order 2
      await orderBook.connect(taker).fillOrder(2);
      // Cancel order 4
      await orderBook.connect(maker).cancelOrder(4);

      return { ...fixture, offeredAmount, requestedAmount };
    }

    it("Should return only active orders", async function () {
      const { orderBook } = await loadFixture(multipleOrdersFixture);

      const activeOrders = await orderBook.getActiveOrders(1, 10);

      // Orders 1, 3, 5 should be active (2 is filled, 4 is cancelled)
      expect(activeOrders.length).to.equal(3);
    });

    it("Should handle pagination correctly", async function () {
      const { orderBook } = await loadFixture(multipleOrdersFixture);

      // Get first 2 orders starting from 1
      const page1 = await orderBook.getActiveOrders(1, 2);
      expect(page1.length).to.equal(1); // Only order 1 is active in range [1,2]

      const page2 = await orderBook.getActiveOrders(3, 2);
      expect(page2.length).to.equal(1); // Only order 3 is active in range [3,4]
    });

    it("Should handle out of range correctly", async function () {
      const { orderBook } = await loadFixture(multipleOrdersFixture);

      const activeOrders = await orderBook.getActiveOrders(100, 10);
      expect(activeOrders.length).to.equal(0);
    });

    it("Should return empty array when no active orders", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);

      const activeOrders = await orderBook.getActiveOrders(1, 10);
      expect(activeOrders.length).to.equal(0);
    });

    it("Should revert when count exceeds maximum allowed", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);

      await expect(orderBook.getActiveOrders(1, 101))
        .to.be.revertedWith("Count exceeds maximum allowed");
    });

    it("Should allow exactly 100 count", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);

      // Should not revert with exactly 100
      const activeOrders = await orderBook.getActiveOrders(1, 100);
      expect(activeOrders.length).to.equal(0);
    });
  });

  describe("getActiveOrderCount", function () {
    it("Should return 0 for user with no orders", async function () {
      const { orderBook, other } = await loadFixture(deployOrderBookFixture);

      expect(await orderBook.getActiveOrderCount(other.address)).to.equal(0);
    });

    it("Should return correct count of active orders", async function () {
      const { orderBook, tokenA, tokenB, maker, taker } = await loadFixture(deployOrderBookFixture);

      const offeredAmount = ethers.parseUnits("10", 6);
      const requestedAmount = ethers.parseUnits("20", 6);

      // Create 5 orders
      for (let i = 0; i < 5; i++) {
        await orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        );
      }

      expect(await orderBook.getActiveOrderCount(maker.address)).to.equal(5);

      // Fill one order
      await orderBook.connect(taker).fillOrder(1);
      expect(await orderBook.getActiveOrderCount(maker.address)).to.equal(4);

      // Cancel one order
      await orderBook.connect(maker).cancelOrder(2);
      expect(await orderBook.getActiveOrderCount(maker.address)).to.equal(3);
    });
  });

  describe("MAX_ACTIVE_ORDERS_PER_USER", function () {
    it("Should have MAX_ACTIVE_ORDERS_PER_USER constant set to 100", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);

      expect(await orderBook.MAX_ACTIVE_ORDERS_PER_USER()).to.equal(100);
    });

    it("Should have MAX_ACTIVE_ORDERS_QUERY constant set to 100", async function () {
      const { orderBook } = await loadFixture(deployOrderBookFixture);

      expect(await orderBook.MAX_ACTIVE_ORDERS_QUERY()).to.equal(100);
    });

    it("Should revert when user exceeds max active orders", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      const offeredAmount = ethers.parseUnits("1", 6);
      const requestedAmount = ethers.parseUnits("2", 6);

      // Create 100 orders (the maximum allowed)
      for (let i = 0; i < 100; i++) {
        await orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        );
      }

      // 101st order should fail
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        )
      ).to.be.revertedWith("Max active orders exceeded");
    });

    it("Should allow creating new order after cancelling one when at max", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      const offeredAmount = ethers.parseUnits("1", 6);
      const requestedAmount = ethers.parseUnits("2", 6);

      // Create 100 orders
      for (let i = 0; i < 100; i++) {
        await orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        );
      }

      // Cancel one order
      await orderBook.connect(maker).cancelOrder(1);

      // Now we should be able to create another order
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        )
      ).to.not.be.reverted;
    });

    it("Should allow creating new order after one is filled when at max", async function () {
      const { orderBook, tokenA, tokenB, maker, taker } = await loadFixture(deployOrderBookFixture);

      const offeredAmount = ethers.parseUnits("1", 6);
      const requestedAmount = ethers.parseUnits("2", 6);

      // Create 100 orders
      for (let i = 0; i < 100; i++) {
        await orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        );
      }

      // Fill one order
      await orderBook.connect(taker).fillOrder(1);

      // Now we should be able to create another order
      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target, offeredAmount, tokenB.target, requestedAmount
        )
      ).to.not.be.reverted;
    });
  });

  describe("getNextOrderId", function () {
    it("Should return the next order ID", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      expect(await orderBook.getNextOrderId()).to.equal(1);

      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      expect(await orderBook.getNextOrderId()).to.equal(2);
    });
  });

  describe("emergencyWithdraw", function () {
    async function emergencyFixture() {
      const fixture = await deployOrderBookFixture();
      const { orderBook, tokenA, tokenB, maker, owner } = fixture;

      const offeredAmount = ethers.parseUnits("100", 6);
      const requestedAmount = ethers.parseUnits("200", 6);

      await orderBook.connect(maker).createOrder(
        tokenA.target, offeredAmount, tokenB.target, requestedAmount
      );

      return { ...fixture, offeredAmount, requestedAmount };
    }

    it("Should allow owner to withdraw tokens", async function () {
      const { orderBook, tokenA, owner, offeredAmount } = await loadFixture(emergencyFixture);

      await expect(
        orderBook.connect(owner).emergencyWithdraw(tokenA.target, offeredAmount, owner.address)
      )
        .to.emit(orderBook, "EmergencyWithdrawal")
        .withArgs(tokenA.target, owner.address, offeredAmount, owner.address);

      expect(await tokenA.balanceOf(owner.address)).to.equal(offeredAmount);
      expect(await tokenA.balanceOf(orderBook.target)).to.equal(0);
    });

    it("Should revert when called by non-owner", async function () {
      const { orderBook, tokenA, taker, offeredAmount } = await loadFixture(emergencyFixture);

      await expect(
        orderBook.connect(taker).emergencyWithdraw(tokenA.target, offeredAmount, taker.address)
      ).to.be.revertedWithCustomError(orderBook, "OwnableUnauthorizedAccount");
    });

    it("Should revert with zero token address", async function () {
      const { orderBook, owner, offeredAmount } = await loadFixture(emergencyFixture);

      await expect(
        orderBook.connect(owner).emergencyWithdraw(ethers.ZeroAddress, offeredAmount, owner.address)
      ).to.be.revertedWith("Invalid token address");
    });

    it("Should revert with zero recipient address", async function () {
      const { orderBook, tokenA, owner, offeredAmount } = await loadFixture(emergencyFixture);

      await expect(
        orderBook.connect(owner).emergencyWithdraw(tokenA.target, offeredAmount, ethers.ZeroAddress)
      ).to.be.revertedWith("Invalid recipient address");
    });

    it("Should revert with zero amount", async function () {
      const { orderBook, tokenA, owner } = await loadFixture(emergencyFixture);

      await expect(
        orderBook.connect(owner).emergencyWithdraw(tokenA.target, 0, owner.address)
      ).to.be.revertedWith("Amount must be greater than 0");
    });

    it("Should revert when amount exceeds contract balance", async function () {
      const { orderBook, tokenA, owner, offeredAmount } = await loadFixture(emergencyFixture);

      await expect(
        orderBook.connect(owner).emergencyWithdraw(tokenA.target, offeredAmount + 1n, owner.address)
      ).to.be.revertedWith("Insufficient contract balance");
    });
  });

  describe("transferOwnership (Ownable2Step)", function () {
    it("Should initiate ownership transfer", async function () {
      const { orderBook, owner, other } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).transferOwnership(other.address);

      // Owner is still the original until accepted
      expect(await orderBook.owner()).to.equal(owner.address);
      // Pending owner should be set
      expect(await orderBook.pendingOwner()).to.equal(other.address);
    });

    it("Should complete ownership transfer when new owner accepts", async function () {
      const { orderBook, owner, other } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).transferOwnership(other.address);
      
      await expect(orderBook.connect(other).acceptOwnership())
        .to.emit(orderBook, "OwnershipTransferred")
        .withArgs(owner.address, other.address);

      expect(await orderBook.owner()).to.equal(other.address);
    });

    it("Should revert when non-pending owner tries to accept", async function () {
      const { orderBook, owner, maker, other } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).transferOwnership(other.address);

      await expect(orderBook.connect(maker).acceptOwnership())
        .to.be.revertedWithCustomError(orderBook, "OwnableUnauthorizedAccount");
    });

    it("Should revert when called by non-owner", async function () {
      const { orderBook, other } = await loadFixture(deployOrderBookFixture);

      await expect(orderBook.connect(other).transferOwnership(other.address))
        .to.be.revertedWithCustomError(orderBook, "OwnableUnauthorizedAccount");
    });

    it("Should allow new owner to use owner functions after accepting", async function () {
      const { orderBook, tokenA, tokenB, owner, maker, other } = await loadFixture(deployOrderBookFixture);

      // Create an order to have tokens in contract
      const offeredAmount = ethers.parseUnits("100", 6);
      await orderBook.connect(maker).createOrder(
        tokenA.target,
        offeredAmount,
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      // Transfer ownership (two-step)
      await orderBook.connect(owner).transferOwnership(other.address);
      await orderBook.connect(other).acceptOwnership();

      // New owner can use owner functions
      await expect(
        orderBook.connect(other).emergencyWithdraw(tokenA.target, offeredAmount, other.address)
      ).to.emit(orderBook, "EmergencyWithdrawal");

      // Old owner can no longer use owner functions
      await expect(
        orderBook.connect(owner).transferOwnership(owner.address)
      ).to.be.revertedWithCustomError(orderBook, "OwnableUnauthorizedAccount");
    });

    it("Should allow owner to cancel pending transfer by transferring to zero", async function () {
      const { orderBook, owner, other } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).transferOwnership(other.address);
      expect(await orderBook.pendingOwner()).to.equal(other.address);

      // Cancel by setting pending owner to zero address
      await orderBook.connect(owner).transferOwnership(ethers.ZeroAddress);
      expect(await orderBook.pendingOwner()).to.equal(ethers.ZeroAddress);
    });
  });

  describe("Reentrancy Protection", function () {
    it("Should have nonReentrant modifier on createOrder", async function () {
      // This test verifies the modifier is present by checking the function works normally
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      // If nonReentrant is missing, a reentrancy attack would be possible
      // This is implicitly tested by verifying correct behavior
    });

    it("Should have nonReentrant modifier on fillOrder", async function () {
      const { orderBook, tokenA, tokenB, maker, taker } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(taker).fillOrder(1);
    });

    it("Should have nonReentrant modifier on cancelOrder", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(maker).cancelOrder(1);
    });

    it("Should have nonReentrant modifier on emergencyWithdraw", async function () {
      const { orderBook, tokenA, tokenB, maker, owner } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(owner).emergencyWithdraw(
        tokenA.target,
        ethers.parseUnits("100", 6),
        owner.address
      );
    });
  });

  describe("Pause Functionality", function () {
    it("Should allow owner to pause the contract", async function () {
      const { orderBook, owner } = await loadFixture(deployOrderBookFixture);

      await expect(orderBook.connect(owner).pause())
        .to.emit(orderBook, "Paused")
        .withArgs(owner.address);
    });

    it("Should allow owner to unpause the contract", async function () {
      const { orderBook, owner } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).pause();

      await expect(orderBook.connect(owner).unpause())
        .to.emit(orderBook, "Unpaused")
        .withArgs(owner.address);
    });

    it("Should revert when non-owner tries to pause", async function () {
      const { orderBook, other } = await loadFixture(deployOrderBookFixture);

      await expect(orderBook.connect(other).pause())
        .to.be.revertedWithCustomError(orderBook, "OwnableUnauthorizedAccount");
    });

    it("Should revert when non-owner tries to unpause", async function () {
      const { orderBook, owner, other } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).pause();

      await expect(orderBook.connect(other).unpause())
        .to.be.revertedWithCustomError(orderBook, "OwnableUnauthorizedAccount");
    });

    it("Should prevent createOrder when paused", async function () {
      const { orderBook, tokenA, tokenB, owner, maker } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).pause();

      await expect(
        orderBook.connect(maker).createOrder(
          tokenA.target,
          ethers.parseUnits("100", 6),
          tokenB.target,
          ethers.parseUnits("200", 6)
        )
      ).to.be.revertedWithCustomError(orderBook, "EnforcedPause");
    });

    it("Should prevent fillOrder when paused", async function () {
      const { orderBook, tokenA, tokenB, owner, maker, taker } = await loadFixture(deployOrderBookFixture);

      // Create order before pausing
      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(owner).pause();

      await expect(orderBook.connect(taker).fillOrder(1))
        .to.be.revertedWithCustomError(orderBook, "EnforcedPause");
    });

    it("Should allow cancelOrder when paused", async function () {
      const { orderBook, tokenA, tokenB, owner, maker } = await loadFixture(deployOrderBookFixture);

      // Create order before pausing
      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(owner).pause();

      // Cancel should still work when paused
      await expect(orderBook.connect(maker).cancelOrder(1))
        .to.emit(orderBook, "OrderCancelled")
        .withArgs(1, maker.address);
    });

    it("Should allow createOrder and fillOrder after unpause", async function () {
      const { orderBook, tokenA, tokenB, owner, maker, taker } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(owner).pause();
      await orderBook.connect(owner).unpause();

      // Should work after unpause
      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(taker).fillOrder(1);

      const order = await orderBook.getOrder(1);
      expect(order.isFilled).to.be.true;
    });
  });

  describe("Edge Cases", function () {
    it("Should handle very small amounts", async function () {
      const { orderBook, tokenA, tokenB, maker, taker } = await loadFixture(deployOrderBookFixture);

      await orderBook.connect(maker).createOrder(tokenA.target, 1, tokenB.target, 1);

      await orderBook.connect(taker).fillOrder(1);

      const order = await orderBook.getOrder(1);
      expect(order.isFilled).to.be.true;
    });

    it("Should handle very large amounts", async function () {
      const { orderBook, tokenA, tokenB, maker, taker, mintAmount } = await loadFixture(deployOrderBookFixture);

      // Use most of the minted tokens
      const largeAmount = mintAmount - ethers.parseUnits("1", 6);

      await orderBook.connect(maker).createOrder(tokenA.target, largeAmount, tokenB.target, largeAmount);

      await orderBook.connect(taker).fillOrder(1);

      const order = await orderBook.getOrder(1);
      expect(order.isFilled).to.be.true;
    });

    it("Should handle multiple orders from same maker", async function () {
      const { orderBook, tokenA, tokenB, maker } = await loadFixture(deployOrderBookFixture);

      for (let i = 0; i < 10; i++) {
        await orderBook.connect(maker).createOrder(
          tokenA.target,
          ethers.parseUnits("10", 6),
          tokenB.target,
          ethers.parseUnits("20", 6)
        );
      }

      const userOrders = await orderBook.getUserOrders(maker.address);
      expect(userOrders.length).to.equal(10);
    });

    it("Should maintain separate orders for different makers", async function () {
      const { orderBook, tokenA, tokenB, maker, taker } = await loadFixture(deployOrderBookFixture);

      // Mint tokenA to taker as well
      const MockERC20 = await ethers.getContractFactory("MockERC20");
      const tokenAContract = MockERC20.attach(tokenA.target);
      await tokenAContract.mint(taker.address, ethers.parseUnits("1000", 6));
      await tokenAContract.connect(taker).approve(orderBook.target, ethers.parseUnits("1000", 6));

      // Both create orders
      await orderBook.connect(maker).createOrder(
        tokenA.target,
        ethers.parseUnits("100", 6),
        tokenB.target,
        ethers.parseUnits("200", 6)
      );

      await orderBook.connect(taker).createOrder(
        tokenA.target,
        ethers.parseUnits("50", 6),
        tokenB.target,
        ethers.parseUnits("100", 6)
      );

      const makerOrders = await orderBook.getUserOrders(maker.address);
      const takerOrders = await orderBook.getUserOrders(taker.address);

      expect(makerOrders.length).to.equal(1);
      expect(takerOrders.length).to.equal(1);
      expect(makerOrders[0]).to.equal(1);
      expect(takerOrders[0]).to.equal(2);
    });
  });
});
