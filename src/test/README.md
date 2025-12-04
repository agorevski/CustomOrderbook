# OrderBook Test Suite

This directory contains the test suite for the OrderBook smart contract.

## Test Script: `test_orderbook.py`

A comprehensive Python test script that validates the OrderBook contract functionality by:

1. **Loading Configuration** - Reads deployment and wallet configuration from JSON files
2. **Pre-condition Verification** - Checks that test wallets have the correct token balances
3. **Order Creation** - Creates an order from the ask_wallet
4. **Order Fulfillment** - Fills the order from the fill_wallet
5. **Post-condition Verification** - Validates the token swap was successful

## Prerequisites

- Python 3.8 or higher
- Access to the Tenderly network (configured in `deployment_config.json`)
- Test wallets with appropriate token balances (configured in `test_wallets.json`)

## Installation

1. Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install web3>=6.0.0 eth-account>=0.9.0
```

## Configuration Files

The test script requires the following configuration files:

### 1. `deployments/OrderBook_tenderly.json`
Contains the deployed contract address and network information.

### 2. `src/deploy/deployment_config.json`
Contains the RPC URL for the Tenderly network.

### 3. `src/test/test_wallets.json`
Contains test wallet configurations with private keys and expected token amounts.

**Structure:**
```json
{
    "ask_wallet": {
        "private_key": "...",
        "address": "0x...",
        "have_address": "0x...",  // Token to offer (e.g., USDC)
        "have_amount": 100,
        "want_address": "0x...",  // Token to request (e.g., Token B)
        "want_amount": 50000
    },
    "fill_wallet": {
        "private_key": "...",
        "address": "0x...",
        "have_address": "0x...",  // Token to offer (must match ask_wallet.want_address)
        "have_amount": 50000,
        "want_address": "0x...",  // Token to request (must match ask_wallet.have_address)
        "want_amount": 100
    }
}
```

### 4. `deployments/OrderBook_abi.json`
Contains the contract ABI for interaction.

## Running the Tests

From the project root directory:

```bash
python src/test/test_orderbook.py
```

Or from the test directory:

```bash
cd src/test
python test_orderbook.py
```

## Test Flow

The test executes the following steps:

### Step 1: Configuration Loading
- Loads deployment configuration
- Loads network configuration
- Loads test wallet configuration
- Loads contract ABI

### Step 2: Network Connection
- Connects to Tenderly network via RPC
- Initializes Web3 instance
- Verifies connection and chain ID

### Step 3: Pre-condition Verification
- **Ask Wallet**: Verifies it has the required amount of tokens to offer and no tokens it wants
- **Fill Wallet**: Verifies it has the required amount of tokens to offer and no tokens it wants

### Step 4: Order Creation
1. Approves OrderBook contract to spend tokens from ask_wallet
2. Creates an order offering tokens for the desired tokens
3. Captures the order ID from the transaction receipt
4. Verifies the order details

### Step 5: Order Fulfillment
1. Approves OrderBook contract to spend tokens from fill_wallet
2. Fills the order using the captured order ID
3. Confirms the transaction

### Step 6: Post-condition Verification
- Verifies ask_wallet received the requested tokens and sent the offered tokens
- Verifies fill_wallet received the offered tokens and sent the requested tokens
- Verifies the order is marked as filled in the contract
- Reports final balances for both wallets

## Expected Output

The script provides colorized output with the following indicators:

- ✓ **Green**: Successful operations
- ✗ **Red**: Failed operations or errors
- ℹ **Cyan**: Informational messages
- ⚠ **Yellow**: Warnings

### Success Example:
```
================================================================================
                      OrderBook Contract Test Suite                      
================================================================================

ℹ Step 1: Loading configuration files...
✓ Contract Address: 0xf7b968F1657196eF0186783FAF19aBBE2484dc3B
✓ RPC URL: https://virtual.arbitrum.us-west.rpc.tenderly.co/...

... [additional output] ...

================================================================================
                              Test Results                              
================================================================================

✓ ALL TESTS PASSED! ✓

ℹ Test Summary:
ℹ   - Order 1 created successfully
ℹ   - Order 1 filled successfully
ℹ   - 100 USDC swapped for 50000 Token B
ℹ   - All balance checks passed
```

## Exit Codes

- **0**: All tests passed
- **1**: One or more tests failed or an error occurred

## Troubleshooting

### Connection Issues
- Verify the RPC URL in `deployment_config.json` is correct and accessible
- Check network connectivity to Tenderly

### Insufficient Balance Errors
- Ensure test wallets have the required token balances
- Verify token addresses match the deployed tokens on the network

### Transaction Failures
- Check that the contract address is correct
- Verify wallets have sufficient ETH/gas tokens for transactions
- Ensure tokens are not fee-on-transfer tokens (not supported by OrderBook)

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.8 or higher

## Token Addresses (Tenderly/Arbitrum)

The test wallets are configured with these token addresses:

- **USDC**: `0xaf88d065e77c8cC2239327C5EDb3A432268e5831`
- **Token B**: `0x2433D6AC11193b4695D9ca73530de93c538aD18a`

Both tokens are assumed to have 6 decimal places.

## Security Notes

⚠️ **WARNING**: The `test_wallets.json` file contains private keys for test purposes only. 

- **NEVER** use these private keys on mainnet
- **NEVER** send real funds to these addresses
- These wallets should only be used on test networks (Tenderly, testnets, etc.)
- Keep this file secure and out of version control if using real test funds

## Additional Information

For more information about the OrderBook contract, see:
- `src/contracts/OrderBook.sol` - Contract source code
- `DEPLOYMENT.md` - Deployment instructions
- `QUICKSTART.md` - Quick start guide
