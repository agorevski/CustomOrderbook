// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable2Step.sol";

/**
 * @title OrderBook
 * @dev A decentralized exchange order book supporting any ERC20 token pairs
 * Allows users to create orders for any two tokens and fill them atomically
 * 
 * SECURITY CONSIDERATIONS:
 * - This contract is NOT compatible with fee-on-transfer tokens (e.g., USDT on some chains, reflection tokens)
 * - Using fee-on-transfer tokens will cause orders to fail or become stuck
 * - Always ensure tokens have been approved before calling fillOrder()
 * - Emergency withdrawal function exists for admin to recover stuck funds
 * 
 * @notice Version 1.2 - Security Hardened with Ownable2Step
 */
contract OrderBook is ReentrancyGuard, Ownable2Step, Pausable {
    using SafeERC20 for IERC20;

    // Order struct
    struct Order {
        address maker;
        address offeredToken;
        uint256 offeredAmount;
        address requestedToken;
        uint256 requestedAmount;
        bool isFilled;
        bool isCancelled;
    }

    // State variables
    uint256 private nextOrderId;
    mapping(uint256 => Order) public orders;
    mapping(address => uint256[]) public userOrders;
    
    // Constants
    uint256 public constant MAX_ACTIVE_ORDERS_PER_USER = 100;
    uint256 public constant MAX_ACTIVE_ORDERS_QUERY = 100;

    // Events
    event OrderCreated(
        uint256 indexed orderId,
        address indexed maker,
        address offeredToken,
        uint256 offeredAmount,
        address requestedToken,
        uint256 requestedAmount
    );

    event OrderFilled(
        uint256 indexed orderId,
        address indexed taker,
        address maker
    );

    event OrderCancelled(
        uint256 indexed orderId,
        address indexed maker
    );

    /**
     * @dev Constructor initializes the order book
     */
    constructor() Ownable(msg.sender) {
        nextOrderId = 1;
    }

    /**
     * @dev Create an order to exchange one token for another
     * @param offeredToken Address of the token being offered
     * @param offeredAmount Amount of the offered token
     * @param requestedToken Address of the token being requested
     * @param requestedAmount Amount of the requested token
     * @return orderId The ID of the created order
     * 
     * @notice WARNING: Do NOT use fee-on-transfer tokens (tokens that deduct fees during transfer)
     * as they will cause the order to become stuck and unfillable.
     */
    function createOrder(
        address offeredToken,
        uint256 offeredAmount,
        address requestedToken,
        uint256 requestedAmount
    )
        external 
        nonReentrant
        whenNotPaused
        returns (uint256)
    {
        require(offeredToken != address(0), "Invalid offered token address");
        require(requestedToken != address(0), "Invalid requested token address");
        require(offeredToken.code.length > 0, "Offered token is not a contract");
        require(requestedToken.code.length > 0, "Requested token is not a contract");
        require(offeredToken != requestedToken, "Tokens must be different");
        require(offeredAmount > 0, "Offered amount must be greater than 0");
        require(requestedAmount > 0, "Requested amount must be greater than 0");
        
        // Check user hasn't exceeded max active orders
        require(
            _getActiveOrderCount(msg.sender) < MAX_ACTIVE_ORDERS_PER_USER,
            "Max active orders exceeded"
        );

        // Transfer offered token from maker to contract
        IERC20(offeredToken).safeTransferFrom(msg.sender, address(this), offeredAmount);

        uint256 orderId = nextOrderId++;
        
        orders[orderId] = Order({
            maker: msg.sender,
            offeredToken: offeredToken,
            offeredAmount: offeredAmount,
            requestedToken: requestedToken,
            requestedAmount: requestedAmount,
            isFilled: false,
            isCancelled: false
        });

        userOrders[msg.sender].push(orderId);

        emit OrderCreated(
            orderId,
            msg.sender,
            offeredToken,
            offeredAmount,
            requestedToken,
            requestedAmount
        );

        return orderId;
    }

    /**
     * @dev Fill an existing order (full fill only)
     * @param orderId The ID of the order to fill
     * 
     * @notice Ensure you have sufficient balance and have approved this contract
     * to spend the requested token amount before calling this function.
     */
    function fillOrder(uint256 orderId) external nonReentrant whenNotPaused {
        Order storage order = orders[orderId];
        
        // CHECK: Validate order state
        require(order.maker != address(0), "Order does not exist");
        require(!order.isFilled, "Order already filled");
        require(!order.isCancelled, "Order cancelled");
        require(order.maker != msg.sender, "Cannot fill your own order");

        // CHECK: Validate taker has sufficient balance and allowance
        require(
            IERC20(order.requestedToken).balanceOf(msg.sender) >= order.requestedAmount,
            "Insufficient balance to fill order"
        );
        require(
            IERC20(order.requestedToken).allowance(msg.sender, address(this)) >= order.requestedAmount,
            "Insufficient allowance to fill order"
        );

        // EFFECTS: Mark order as filled BEFORE external interactions (CEI pattern)
        order.isFilled = true;

        // INTERACTIONS: Transfer tokens after state changes
        // Transfer requested token from taker to maker
        IERC20(order.requestedToken).safeTransferFrom(
            msg.sender,
            order.maker,
            order.requestedAmount
        );

        // Transfer offered token from contract to taker
        IERC20(order.offeredToken).safeTransfer(
            msg.sender,
            order.offeredAmount
        );

        emit OrderFilled(orderId, msg.sender, order.maker);
    }

    /**
     * @dev Cancel an unfilled order (only by maker)
     * @param orderId The ID of the order to cancel
     */
    function cancelOrder(uint256 orderId) external nonReentrant {
        Order storage order = orders[orderId];
        
        require(order.maker != address(0), "Order does not exist");
        require(order.maker == msg.sender, "Only maker can cancel");
        require(!order.isFilled, "Order already filled");
        require(!order.isCancelled, "Order already cancelled");

        // Mark order as cancelled
        order.isCancelled = true;

        // Return offered token to maker
        IERC20(order.offeredToken).safeTransfer(
            order.maker,
            order.offeredAmount
        );

        emit OrderCancelled(orderId, msg.sender);
    }

    /**
     * @dev Get order details
     * @param orderId The ID of the order
     * @return Order struct
     */
    function getOrder(uint256 orderId) external view returns (Order memory) {
        require(orders[orderId].maker != address(0), "Order does not exist");
        return orders[orderId];
    }

    /**
     * @dev Get all order IDs for a user
     * @param user The address of the user
     * @return Array of order IDs
     */
    function getUserOrders(address user) external view returns (uint256[] memory) {
        return userOrders[user];
    }

    /**
     * @dev Get active (unfilled and uncancelled) orders
     * @param startId Starting order ID
     * @param count Number of orders to return (max 100)
     * @return Array of active orders
     * 
     * @notice This function enforces a maximum query size of 100 orders to prevent
     * out-of-gas errors.
     */
    function getActiveOrders(uint256 startId, uint256 count) 
        external 
        view 
        returns (Order[] memory) 
    {
        require(count <= MAX_ACTIVE_ORDERS_QUERY, "Count exceeds maximum allowed");
        
        uint256 endId = startId + count;
        if (endId > nextOrderId) {
            endId = nextOrderId;
        }

        // Single-pass optimized approach: create temporary array with max size
        Order[] memory tempOrders = new Order[](count);
        uint256 activeCount = 0;
        
        for (uint256 i = startId; i < endId; i++) {
            if (orders[i].maker != address(0) && !orders[i].isFilled && !orders[i].isCancelled) {
                tempOrders[activeCount] = orders[i];
                activeCount++;
            }
        }

        // Create final array with exact size and copy active orders
        Order[] memory activeOrders = new Order[](activeCount);
        for (uint256 i = 0; i < activeCount; i++) {
            activeOrders[i] = tempOrders[i];
        }

        return activeOrders;
    }
    
    /**
     * @dev Get the count of active (unfilled and uncancelled) orders for a user
     * @param user The address of the user
     * @return count The number of active orders
     */
    function getActiveOrderCount(address user) external view returns (uint256) {
        return _getActiveOrderCount(user);
    }
    
    /**
     * @dev Internal function to count active orders for a user
     * @param user The address of the user
     * @return count The number of active orders
     */
    function _getActiveOrderCount(address user) internal view returns (uint256) {
        uint256[] memory orderIds = userOrders[user];
        uint256 count = 0;
        
        for (uint256 i = 0; i < orderIds.length; i++) {
            Order storage order = orders[orderIds[i]];
            if (!order.isFilled && !order.isCancelled) {
                count++;
            }
        }
        
        return count;
    }

    /**
     * @dev Get the next order ID
     * @return The next order ID that will be used
     */
    function getNextOrderId() external view returns (uint256) {
        return nextOrderId;
    }

    /**
     * @dev Emergency function to withdraw any ERC20 token from the contract
     * @param token Address of the token to withdraw
     * @param amount Amount to withdraw
     * @param recipient Address to receive the withdrawn tokens
     * 
     * @notice This function is for emergency use only to recover stuck funds.
     * It should only be used in exceptional circumstances such as:
     * - Tokens stuck due to failed orders
     * - Fee-on-transfer tokens that caused issues
     * - Other unforeseen contract states
     * 
     * WARNING: Using this function on active orders will break those orders.
     * Only use after careful consideration and potentially after a timelock period.
     */
    function emergencyWithdraw(
        address token,
        uint256 amount,
        address recipient
    ) 
        external 
        onlyOwner 
        nonReentrant 
    {
        require(token != address(0), "Invalid token address");
        require(recipient != address(0), "Invalid recipient address");
        require(amount > 0, "Amount must be greater than 0");
        
        uint256 contractBalance = IERC20(token).balanceOf(address(this));
        require(contractBalance >= amount, "Insufficient contract balance");

        IERC20(token).safeTransfer(recipient, amount);

        emit EmergencyWithdrawal(token, recipient, amount, msg.sender);
    }

    /**
     * @dev Pause the contract, preventing createOrder and fillOrder
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @dev Unpause the contract
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    // Additional events
    event EmergencyWithdrawal(
        address indexed token,
        address indexed recipient,
        uint256 amount,
        address indexed admin
    );
}
