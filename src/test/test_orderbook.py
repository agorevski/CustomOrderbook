#!/usr/bin/env python3
"""
OrderBook Contract Integrated Test Script

This script provides a complete test lifecycle:
1. Generate 3 brand new vanity accounts (or load from .env with --use-env)
2. Fund the accounts with ETH and tokens (skipped with --use-env)
3. Deploy OrderBook.sol contract to Tenderly
4. Run comprehensive tests on the deployed contract

Usage:
    python test_orderbook.py              # Generate new accounts and fund them
    python test_orderbook.py --use-env    # Use pre-funded accounts from .env file
"""

import json
import sys
import os
import argparse
import requests
from pathlib import Path
from web3 import Web3
from solcx import compile_standard, install_solc, set_solc_version
from dotenv import load_dotenv

# Add utils directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "utils"))
from eth_vanity_generator import generate_multiple_addresses
import random


# Color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def load_env_config():
    """Load configuration from .env file for --use-env mode.

    Returns:
        dict: Configuration containing token addresses and account information
    """
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        print_error(f".env file not found at {env_path}")
        print_info("Please copy .env.example to .env and configure your accounts")
        sys.exit(1)

    load_dotenv(env_path)

    # Required environment variables
    required_vars = [
        "TOKEN_A_ADDRESS",
        "TOKEN_B_ADDRESS",
        "DEPLOYMENT_ACCOUNT_ADDRESS",
        "DEPLOYMENT_ACCOUNT_PRIVATE_KEY",
        "ASK_ACCOUNT_ADDRESS",
        "ASK_ACCOUNT_PRIVATE_KEY",
        "FILL_ACCOUNT_ADDRESS",
        "FILL_ACCOUNT_PRIVATE_KEY",
    ]

    # Check for missing variables
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print_error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Build configuration
    config = {
        "token_a_address": os.getenv("TOKEN_A_ADDRESS"),
        "token_b_address": os.getenv("TOKEN_B_ADDRESS"),
        "deployment_account": {
            "checksum_address": Web3.to_checksum_address(
                os.getenv("DEPLOYMENT_ACCOUNT_ADDRESS")
            ),
            "private_key": os.getenv("DEPLOYMENT_ACCOUNT_PRIVATE_KEY"),
        },
        "ask_account": {
            "checksum_address": Web3.to_checksum_address(
                os.getenv("ASK_ACCOUNT_ADDRESS")
            ),
            "private_key": os.getenv("ASK_ACCOUNT_PRIVATE_KEY"),
        },
        "fill_account": {
            "checksum_address": Web3.to_checksum_address(
                os.getenv("FILL_ACCOUNT_ADDRESS")
            ),
            "private_key": os.getenv("FILL_ACCOUNT_PRIVATE_KEY"),
        },
        "token_a_trade_amount": None,
        "token_b_trade_amount": None,
    }

    # Load optional pre-deployed contract address
    config["orderbook_contract_address"] = os.getenv("ORDERBOOK_CONTRACT_ADDRESS")

    # Load optional trade amounts
    token_a_trade_str = os.getenv("TOKEN_A_TRADE_AMOUNT")
    token_b_trade_str = os.getenv("TOKEN_B_TRADE_AMOUNT")

    if token_a_trade_str:
        try:
            config["token_a_trade_amount"] = float(token_a_trade_str)
        except ValueError:
            print_warning(f"Invalid TOKEN_A_TRADE_AMOUNT value: {token_a_trade_str}, using wallet balance")

    if token_b_trade_str:
        try:
            config["token_b_trade_amount"] = float(token_b_trade_str)
        except ValueError:
            print_warning(f"Invalid TOKEN_B_TRADE_AMOUNT value: {token_b_trade_str}, using wallet balance")

    print_success("Loaded configuration from .env file")
    print_info(f"  Token A Address: {config['token_a_address']}")
    print_info(f"  Token B Address: {config['token_b_address']}")
    print_info(
        f"  Deployment Account: {config['deployment_account']['checksum_address']}"
    )
    print_info(f"  Ask Account: {config['ask_account']['checksum_address']}")
    print_info(f"  Fill Account: {config['fill_account']['checksum_address']}")
    if config["token_a_trade_amount"] is not None:
        print_info(f"  Token A Trade Amount: {config['token_a_trade_amount']}")
    else:
        print_info("  Token A Trade Amount: (using wallet balance)")
    if config["token_b_trade_amount"] is not None:
        print_info(f"  Token B Trade Amount: {config['token_b_trade_amount']}")
    else:
        print_info("  Token B Trade Amount: (using wallet balance)")

    return config


def load_json_file(filepath):
    """Load and parse JSON file"""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print_error(f"File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {filepath}: {e}")
        sys.exit(1)


def load_deployed_contract_abi():
    """Load the OrderBook ABI from the deployments directory.
    
    Returns:
        list: The contract ABI
    """
    base_path = Path(__file__).parent.parent.parent
    abi_path = base_path / "deployments" / "OrderBook_abi.json"
    
    if not abi_path.exists():
        print_error(f"OrderBook ABI not found at {abi_path}")
        print_info("Please ensure the contract has been deployed and the ABI file exists")
        sys.exit(1)
    
    print_info(f"Loading ABI from: {abi_path}")
    abi = load_json_file(abi_path)
    print_success("ABI loaded successfully")
    
    return abi


def format_token_amount(amount, decimals=6):
    """Format token amount with decimals"""
    return float(amount) / (10**decimals)


def to_wei_custom(amount, decimals=6):
    """Convert amount to smallest unit based on token decimals"""
    return int(amount * (10**decimals))


def tenderly_rpc_call(rpc_url, method, params):
    """Make a JSON-RPC call to Tenderly"""
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": "1"}

    try:
        response = requests.post(
            rpc_url, json=payload, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print_error(f"RPC Error: {result['error']}")
            sys.exit(1)

        return result.get("result")
    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        sys.exit(1)


def generate_test_accounts():
    """Generate 3 fresh vanity accounts for testing"""
    print_info("Generating 3 fresh test accounts...")
    accounts = generate_multiple_addresses(3)

    deployment_account = accounts[0]
    ask_account = accounts[1]
    fill_account = accounts[2]

    print_success(f"Deployment Account: {deployment_account['checksum_address']}")
    print_info(f"  Private Key: {deployment_account['private_key']}")
    print_success(f"Ask Account: {ask_account['checksum_address']}")
    print_info(f"  Private Key: {ask_account['private_key']}")
    print_success(f"Fill Account: {fill_account['checksum_address']}")
    print_info(f"  Private Key: {fill_account['private_key']}")

    return deployment_account, ask_account, fill_account


def fund_accounts(
    rpc_url,
    deployment_account,
    ask_account,
    fill_account,
    token_a_address=None,
    token_b_address=None,
):
    """Fund accounts with ETH and tokens via Tenderly RPC"""
    print_header("Funding Test Accounts")

    # Use provided token addresses or defaults
    USDC_ADDRESS = token_a_address or "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    TOKEN_B_ADDRESS = token_b_address or "0x2433D6AC11193b4695D9ca73530de93c538aD18a"

    # Fund native balance (10 ETH each)
    print_info("Funding native balance (10 ETH each)...")
    eth_amount = Web3.to_wei(10, "ether")
    eth_amount_hex = hex(eth_amount)

    addresses_to_fund = [
        deployment_account["checksum_address"],
        ask_account["checksum_address"],
        fill_account["checksum_address"],
    ]

    tenderly_rpc_call(
        rpc_url, "tenderly_setBalance", [addresses_to_fund, eth_amount_hex]
    )
    print_success("Native balance funded for all accounts")

    usdc_amount = random.uniform(1, 10) * (10**6)
    print_info(f"Funding Ask Account with {usdc_amount / (10**6):.2f} Token A...")
    usdc_amount_hex = hex(int(usdc_amount))

    tenderly_rpc_call(
        rpc_url,
        "tenderly_setErc20Balance",
        [USDC_ADDRESS, [ask_account["checksum_address"]], usdc_amount_hex],
    )
    print_success(f"Ask Account funded with Token A")

    # Fund Fill Account with 50,000 Token B (6 decimals)
    token_b_amount = random.uniform(50000, 100000) * (10**6)
    print_info(f"Funding Fill Account with {token_b_amount / (10**6):.2f} Token B...")
    token_b_amount_hex = hex(int(token_b_amount))

    tenderly_rpc_call(
        rpc_url,
        "tenderly_setErc20Balance",
        [TOKEN_B_ADDRESS, [fill_account["checksum_address"]], token_b_amount_hex],
    )
    print_success(f"Fill Account funded with Token B")

    print_success("All accounts funded successfully!")


def compile_orderbook_contract():
    """Compile the OrderBook.sol contract"""
    print_header("Compiling OrderBook Contract")

    # Install and set solc version
    solc_version = "0.8.20"
    print_info(f"Installing Solidity compiler version {solc_version}...")
    install_solc(solc_version)
    set_solc_version(solc_version)
    print_success(f"Solidity compiler {solc_version} installed")

    # Read contract source
    contract_path = Path(__file__).parent.parent / "contracts" / "OrderBook.sol"
    if not contract_path.exists():
        print_error("OrderBook.sol not found in src/contracts directory")
        sys.exit(1)

    with open(contract_path, "r") as f:
        contract_source = f.read()

    print_info("Locating node_modules for OpenZeppelin imports...")

    # Try to find node_modules
    project_root = Path(__file__).parent.parent.parent
    possible_paths = [
        project_root / "node_modules",
        project_root.parent / "node_modules",
        Path("C:/GIT/node_modules"),
    ]

    node_modules_path = None
    for path in possible_paths:
        if path.exists():
            node_modules_path = path
            break

    if not node_modules_path:
        print_error(
            "node_modules directory not found. Please run 'npm install @openzeppelin/contracts'"
        )
        sys.exit(1)

    print_success(f"Found node_modules at: {node_modules_path}")

    print_info("Compiling contract...")

    # Compile with import remapping
    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {"OrderBook.sol": {"content": contract_source}},
            "settings": {
                "remappings": [f"@openzeppelin/={node_modules_path}/@openzeppelin/"],
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {
                    "*": {
                        "*": [
                            "abi",
                            "metadata",
                            "evm.bytecode",
                            "evm.bytecode.sourceMap",
                        ]
                    }
                },
            },
        },
        allow_paths=[str(project_root), str(node_modules_path)],
    )

    print_success("Contract compiled successfully")

    # Extract contract data
    contract_data = compiled_sol["contracts"]["OrderBook.sol"]["OrderBook"]

    return {
        "abi": contract_data["abi"],
        "bytecode": contract_data["evm"]["bytecode"]["object"],
    }


def deploy_orderbook_contract(w3, deployment_account, contract_data):
    """Deploy the OrderBook contract using the deployment account"""
    print_header("Deploying OrderBook Contract")

    # Create contract instance
    OrderBook = w3.eth.contract(
        abi=contract_data["abi"], bytecode=contract_data["bytecode"]
    )

    # Get deployer account
    deployer_address = deployment_account["checksum_address"]
    deployer_key = deployment_account["private_key"]

    # Get nonce
    nonce = w3.eth.get_transaction_count(deployer_address)

    print_info(f"Deploying from: {deployer_address}")

    # Estimate gas
    try:
        gas_estimate = OrderBook.constructor().estimate_gas({"from": deployer_address})
        print_success(f"Estimated gas: {gas_estimate}")
    except Exception as e:
        print_warning(f"Could not estimate gas: {e}")
        gas_estimate = 3000000

    # Build transaction
    transaction = OrderBook.constructor().build_transaction(
        {
            "chainId": w3.eth.chain_id,
            "gas": gas_estimate + 100000,  # Add buffer
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "from": deployer_address,
        }
    )

    # Sign transaction
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=deployer_key)

    # Send transaction
    print_info("Sending deployment transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print_success(f"Transaction sent: {tx_hash.hex()}")

    # Wait for receipt
    print_info("Waiting for confirmation...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if tx_receipt["status"] == 1:
        contract_address = tx_receipt["contractAddress"]
        print_success(f"Contract deployed at: {contract_address}")
        print_info(f"Gas used: {tx_receipt['gasUsed']}")
        return contract_address
    else:
        print_error("Contract deployment failed")
        sys.exit(1)


def get_token_balance(w3, token_address, wallet_address):
    """Get ERC20 token balance for a wallet"""
    # Minimal ERC20 ABI for balanceOf
    erc20_abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }
    ]

    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=erc20_abi
    )

    balance = token_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet_address)
    ).call()

    return balance


def approve_token(
    w3, token_address, spender_address, amount, private_key, from_address
):
    """Approve token spending"""
    # Minimal ERC20 ABI for approve
    erc20_abi = [
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        }
    ]

    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=erc20_abi
    )

    # Build transaction
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))

    tx = token_contract.functions.approve(
        Web3.to_checksum_address(spender_address), amount
    ).build_transaction(
        {
            "from": Web3.to_checksum_address(from_address),
            "nonce": nonce,
            "gas": 100000,
            "gasPrice": w3.eth.gas_price,
        }
    )

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt


def create_order(
    w3,
    contract,
    offered_token,
    offered_amount,
    requested_token,
    requested_amount,
    private_key,
    from_address,
):
    """Create an order on the OrderBook"""
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))

    tx = contract.functions.createOrder(
        Web3.to_checksum_address(offered_token),
        offered_amount,
        Web3.to_checksum_address(requested_token),
        requested_amount,
    ).build_transaction(
        {
            "from": Web3.to_checksum_address(from_address),
            "nonce": nonce,
            "gas": 500000,
            "gasPrice": w3.eth.gas_price,
        }
    )

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt


def fill_order(w3, contract, order_id, private_key, from_address):
    """Fill an order on the OrderBook"""
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))

    tx = contract.functions.fillOrder(order_id).build_transaction(
        {
            "from": Web3.to_checksum_address(from_address),
            "nonce": nonce,
            "gas": 500000,
            "gasPrice": w3.eth.gas_price,
        }
    )

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt


def extract_order_id_from_receipt(w3, receipt, contract):
    """Extract order ID from OrderCreated event in transaction receipt"""
    # Get OrderCreated event
    order_created_event = contract.events.OrderCreated()
    logs = order_created_event.process_receipt(receipt)

    if logs:
        return logs[0]["args"]["orderId"]
    return None


def run_orderbook_tests(
    w3,
    contract_address,
    contract_abi,
    ask_account,
    fill_account,
    token_a_address=None,
    token_b_address=None,
    token_a_trade_amount=None,
    token_b_trade_amount=None,
):
    """Run the OrderBook tests

    Args:
        w3: Web3 instance
        contract_address: Deployed OrderBook contract address
        contract_abi: Contract ABI
        ask_account: Account that creates the order (offers Token A, requests Token B)
        fill_account: Account that fills the order (offers Token B, receives Token A)
        token_a_address: Token A address (default: USDC)
        token_b_address: Token B address (default: custom Token B)
        token_a_trade_amount: Optional fixed amount of Token A to trade (in token units, e.g., 5.0)
        token_b_trade_amount: Optional fixed amount of Token B to trade (in token units, e.g., 50000.0)
    """
    print_header("Running OrderBook Tests")

    # Use provided token addresses or defaults
    TOKEN_A_ADDRESS = token_a_address or "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    TOKEN_B_ADDRESS = token_b_address or "0x2433D6AC11193b4695D9ca73530de93c538aD18a"

    print_info(f"Token A Address: {TOKEN_A_ADDRESS}")
    print_info(f"Token B Address: {TOKEN_B_ADDRESS}")

    # Initialize contract
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address), abi=contract_abi
    )

    # Extract wallet info
    ask_address = ask_account["checksum_address"]
    fill_address = fill_account["checksum_address"]

    ask_private_key = ask_account["private_key"]
    fill_private_key = fill_account["private_key"]

    # Expected amounts will be set dynamically based on wallet balances

    # Step 1: Verify pre-conditions
    print_header("Step 1: Verifying Pre-conditions")

    print_info("Checking ask_wallet balances...")
    ask_token_a_balance = get_token_balance(w3, TOKEN_A_ADDRESS, ask_address)
    ask_tokenb_balance = get_token_balance(w3, TOKEN_B_ADDRESS, ask_address)

    print_info(f"  Ask Account ({ask_address}):")
    print_info(f"    Token A Balance: {format_token_amount(ask_token_a_balance, 6)}")
    print_info(f"    Token B Balance: {format_token_amount(ask_tokenb_balance, 6)}")

    # Determine ask_offered_amount: use specified amount from .env or wallet balance
    if token_a_trade_amount is not None:
        # Convert from token units to smallest unit (e.g., 5.0 USDC -> 5000000)
        ask_offered_amount = to_wei_custom(token_a_trade_amount, 6)
        print_info(f"  Using specified Token A trade amount: {token_a_trade_amount}")
        # Validate sufficient balance
        if ask_offered_amount > ask_token_a_balance:
            print_error(
                f"Insufficient Token A balance. Required: {token_a_trade_amount}, "
                f"Available: {format_token_amount(ask_token_a_balance, 6)}"
            )
            sys.exit(1)
    else:
        # Use full wallet balance
        ask_offered_amount = ask_token_a_balance
        print_info("  Using full wallet balance for Token A trade amount")

    if ask_token_a_balance == 0:
        print_error("Ask account has no Token A balance")
        sys.exit(1)

    print_success(
        f"Ask account Token A balance: {format_token_amount(ask_token_a_balance, 6)}"
    )
    print_success(
        f"Token A trade amount: {format_token_amount(ask_offered_amount, 6)}"
    )

    print_info("\nChecking fill_wallet balances...")
    fill_token_a_balance = get_token_balance(w3, TOKEN_A_ADDRESS, fill_address)
    fill_tokenb_balance = get_token_balance(w3, TOKEN_B_ADDRESS, fill_address)

    print_info(f"  Fill Account ({fill_address}):")
    print_info(f"    Token A Balance: {format_token_amount(fill_token_a_balance, 6)}")
    print_info(f"    Token B Balance: {format_token_amount(fill_tokenb_balance, 6)}")

    # Determine ask_requested_amount: use specified amount from .env or wallet balance
    if token_b_trade_amount is not None:
        # Convert from token units to smallest unit (e.g., 50000.0 -> 50000000000)
        ask_requested_amount = to_wei_custom(token_b_trade_amount, 6)
        print_info(f"  Using specified Token B trade amount: {token_b_trade_amount}")
        # Validate sufficient balance
        if ask_requested_amount > fill_tokenb_balance:
            print_error(
                f"Insufficient Token B balance in fill account. Required: {token_b_trade_amount}, "
                f"Available: {format_token_amount(fill_tokenb_balance, 6)}"
            )
            sys.exit(1)
    else:
        # Use full wallet balance
        ask_requested_amount = fill_tokenb_balance
        print_info("  Using full wallet balance for Token B trade amount")

    if fill_tokenb_balance == 0:
        print_error("Fill account has no Token B balance")
        sys.exit(1)

    print_success(
        f"Fill account Token B balance: {format_token_amount(fill_tokenb_balance, 6)}"
    )
    print_success(
        f"Token B trade amount: {format_token_amount(ask_requested_amount, 6)}"
    )

    # Step 2: Approve and create order
    print_header("Step 2: Creating Order from Ask Account")

    print_info(
        f"Approving OrderBook to spend {format_token_amount(ask_offered_amount, 6)} Token A from ask_account..."
    )

    try:
        approve_receipt = approve_token(
            w3,
            TOKEN_A_ADDRESS,
            contract_address,
            ask_offered_amount,
            ask_private_key,
            ask_address,
        )
        print_success(
            f"Approval transaction successful: {approve_receipt['transactionHash'].hex()}"
        )
        print_info(f"  Gas used: {approve_receipt['gasUsed']}")
    except Exception as e:
        print_error(f"Approval failed: {e}")
        sys.exit(1)

    print_info(
        f"\nCreating order: {format_token_amount(ask_offered_amount, 6)} Token A for {format_token_amount(ask_requested_amount, 6)} Token B..."
    )

    try:
        create_receipt = create_order(
            w3,
            contract,
            TOKEN_A_ADDRESS,
            ask_offered_amount,
            TOKEN_B_ADDRESS,
            ask_requested_amount,
            ask_private_key,
            ask_address,
        )
        print_success(
            f"Order created successfully: {create_receipt['transactionHash'].hex()}"
        )
        print_info(f"  Gas used: {create_receipt['gasUsed']}")

        # Extract order ID
        order_id = extract_order_id_from_receipt(w3, create_receipt, contract)
        if order_id:
            print_success(f"  Order ID: {order_id}")
        else:
            print_error("Could not extract order ID from receipt")
            sys.exit(1)

    except Exception as e:
        print_error(f"Order creation failed: {e}")
        sys.exit(1)

    # Verify order was created
    print_info("\nVerifying order details...")
    try:
        order = contract.functions.getOrder(order_id).call()
        # Order is returned as a tuple: (orderId, maker, offeredToken, offeredAmount, requestedToken, requestedAmount, isFilled, isCancelled)
        print_info(f"  Order ID: {order[0]}")
        print_info(f"  Maker: {order[1]}")
        print_info(f"  Offered Token: {order[2]}")
        print_info(f"  Offered Amount: {format_token_amount(order[3], 6)}")
        print_info(f"  Requested Token: {order[4]}")
        print_info(f"  Requested Amount: {format_token_amount(order[5], 6)}")
        print_info(f"  Is Filled: {order[6]}")
        print_info(f"  Is Cancelled: {order[7]}")
        print_success("Order details verified")
    except Exception as e:
        print_error(f"Failed to retrieve order: {e}")
        sys.exit(1)

    # Step 3: Approve and fill order
    print_header("Step 3: Filling Order from Fill Account")

    print_info(
        f"Approving OrderBook to spend {format_token_amount(ask_requested_amount, 6)} Token B from fill_account..."
    )

    try:
        approve_receipt = approve_token(
            w3,
            TOKEN_B_ADDRESS,
            contract_address,
            ask_requested_amount,
            fill_private_key,
            fill_address,
        )
        print_success(
            f"Approval transaction successful: {approve_receipt['transactionHash'].hex()}"
        )
        print_info(f"  Gas used: {approve_receipt['gasUsed']}")
    except Exception as e:
        print_error(f"Approval failed: {e}")
        sys.exit(1)

    print_info(f"\nFilling order {order_id}...")

    try:
        fill_receipt = fill_order(
            w3, contract, order_id, fill_private_key, fill_address
        )
        print_success(
            f"Order filled successfully: {fill_receipt['transactionHash'].hex()}"
        )
        print_info(f"  Gas used: {fill_receipt['gasUsed']}")
    except Exception as e:
        print_error(f"Order fill failed: {e}")
        sys.exit(1)

    # Step 4: Verify post-conditions
    print_header("Step 4: Verifying Post-conditions")

    print_info("Checking final balances...")

    # Ask account final balances
    ask_token_a_final = get_token_balance(w3, TOKEN_A_ADDRESS, ask_address)
    ask_tokenb_final = get_token_balance(w3, TOKEN_B_ADDRESS, ask_address)

    print_info(f"\nAsk Account ({ask_address}):")
    print_info(
        f"  Token A: {format_token_amount(ask_token_a_balance, 6)} → {format_token_amount(ask_token_a_final, 6)}"
    )
    print_info(
        f"  Token B: {format_token_amount(ask_tokenb_balance, 6)} → {format_token_amount(ask_tokenb_final, 6)}"
    )

    # Fill account final balances
    fill_token_a_final = get_token_balance(w3, TOKEN_A_ADDRESS, fill_address)
    fill_tokenb_final = get_token_balance(w3, TOKEN_B_ADDRESS, fill_address)

    print_info(f"\nFill Account ({fill_address}):")
    print_info(
        f"  Token A: {format_token_amount(fill_token_a_balance, 6)} → {format_token_amount(fill_token_a_final, 6)}"
    )
    print_info(
        f"  Token B: {format_token_amount(fill_tokenb_balance, 6)} → {format_token_amount(fill_tokenb_final, 6)}"
    )

    # Verify the swap was successful
    print_info("\nVerifying swap results...")

    success = True

    # Ask account should have received Token B and lost Token A
    expected_ask_token_a = ask_token_a_balance - ask_offered_amount
    expected_ask_tokenb = ask_tokenb_balance + ask_requested_amount

    if ask_token_a_final == expected_ask_token_a:
        print_success(
            f"Ask account Token A balance correct: {format_token_amount(ask_token_a_final, 6)}"
        )
    else:
        print_error(
            f"Ask account Token A balance incorrect. Expected {format_token_amount(expected_ask_token_a, 6)}, got {format_token_amount(ask_token_a_final, 6)}"
        )
        success = False

    if ask_tokenb_final == expected_ask_tokenb:
        print_success(
            f"Ask account Token B balance correct: {format_token_amount(ask_tokenb_final, 6)}"
        )
    else:
        print_error(
            f"Ask account Token B balance incorrect. Expected {format_token_amount(expected_ask_tokenb, 6)}, got {format_token_amount(ask_tokenb_final, 6)}"
        )
        success = False

    # Fill account should have received Token A and lost Token B
    expected_fill_token_a = fill_token_a_balance + ask_offered_amount
    expected_fill_tokenb = fill_tokenb_balance - ask_requested_amount

    if fill_token_a_final == expected_fill_token_a:
        print_success(
            f"Fill account Token A balance correct: {format_token_amount(fill_token_a_final, 6)}"
        )
    else:
        print_error(
            f"Fill account Token A balance incorrect. Expected {format_token_amount(expected_fill_token_a, 6)}, got {format_token_amount(fill_token_a_final, 6)}"
        )
        success = False

    if fill_tokenb_final == expected_fill_tokenb:
        print_success(
            f"Fill account Token B balance correct: {format_token_amount(fill_tokenb_final, 6)}"
        )
    else:
        print_error(
            f"Fill account Token B balance incorrect. Expected {format_token_amount(expected_fill_tokenb, 6)}, got {format_token_amount(fill_tokenb_final, 6)}"
        )
        success = False

    # Verify order is marked as filled
    try:
        order = contract.functions.getOrder(order_id).call()
        # Order tuple: (orderId, maker, offeredToken, offeredAmount, requestedToken, requestedAmount, isFilled, isCancelled)
        if order[6]:  # isFilled is at index 6
            print_success("Order is marked as filled")
        else:
            print_error("Order is not marked as filled")
            success = False
    except Exception as e:
        print_error(f"Failed to check order status: {e}")
        success = False

    return success, order_id


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="OrderBook Contract Integrated Test Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_orderbook.py              # Generate new accounts and fund them
    python test_orderbook.py --use-env    # Use pre-funded accounts from .env file
        """,
    )
    parser.add_argument(
        "--use-env",
        action="store_true",
        help="Use pre-funded accounts and token addresses from .env file instead of generating new accounts",
    )
    return parser.parse_args()


def main():
    """Main test execution"""
    # Parse command-line arguments
    args = parse_arguments()
    use_env = args.use_env

    print_header("OrderBook Contract - Integrated Test Suite")

    if use_env:
        print_info("Mode: Using pre-funded accounts from .env file")
    else:
        print_info("Mode: Generating fresh accounts and funding them")

    # Load network configuration
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "src" / "deploy" / "deployment_config.json"
    network_config = load_json_file(config_path)

    rpc_url = network_config["tenderly"]["rpc_url"]
    print_success(f"RPC URL: {rpc_url}")

    # Connect to blockchain
    print_info("\nConnecting to Tenderly network...")
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print_error("Failed to connect to network")
        sys.exit(1)

    print_success(f"Connected to chain ID: {w3.eth.chain_id}")

    # Initialize variables for token addresses
    token_a_address = None
    token_b_address = None

    # Initialize variables for trade amounts
    token_a_trade_amount = None
    token_b_trade_amount = None

    # Initialize variables for contract
    contract_address = None
    contract_abi = None
    use_predeployed_contract = False

    if use_env:
        # Load configuration from .env file
        print_header("Phase 1: Load Configuration from .env")
        env_config = load_env_config()

        deployment_account = env_config["deployment_account"]
        ask_account = env_config["ask_account"]
        fill_account = env_config["fill_account"]
        token_a_address = env_config["token_a_address"]
        token_b_address = env_config["token_b_address"]
        token_a_trade_amount = env_config["token_a_trade_amount"]
        token_b_trade_amount = env_config["token_b_trade_amount"]

        # Check if a pre-deployed contract address is specified
        if env_config.get("orderbook_contract_address"):
            use_predeployed_contract = True
            contract_address = Web3.to_checksum_address(env_config["orderbook_contract_address"])
            print_info(f"  Pre-deployed Contract: {contract_address}")

        print_header("Phase 2: Skipping Account Funding (using pre-funded accounts)")
        print_info("Accounts are assumed to be pre-funded with ETH and tokens")

        if use_predeployed_contract:
            # Skip compilation and deployment, load ABI from deployments folder
            print_header("Phase 3: Using Pre-deployed Contract")
            print_info(f"Using pre-deployed OrderBook contract at: {contract_address}")
            contract_abi = load_deployed_contract_abi()
        else:
            # Compile and deploy a fresh contract
            print_header("Phase 3: Compile Contract")
            contract_data = compile_orderbook_contract()
            contract_abi = contract_data["abi"]

            print_header("Phase 4: Deploy Contract")
            contract_address = deploy_orderbook_contract(w3, deployment_account, contract_data)
    else:
        # Phase 1: Compile contract
        print_header("Phase 1: Compile Contract")
        contract_data = compile_orderbook_contract()
        contract_abi = contract_data["abi"]

        # Phase 2: Generate accounts
        print_header("Phase 2: Account Generation")
        deployment_account, ask_account, fill_account = generate_test_accounts()

        # Phase 3: Fund accounts
        print_header("Phase 3: Fund Accounts")
        fund_accounts(rpc_url, deployment_account, ask_account, fill_account)

        # Phase 4: Deploy contract
        print_header("Phase 4: Deploy Contract")
        contract_address = deploy_orderbook_contract(w3, deployment_account, contract_data)

    # Phase 5: Run tests
    print_header("Phase 5: Run Tests")
    success, order_id = run_orderbook_tests(
        w3,
        contract_address,
        contract_abi,
        ask_account,
        fill_account,
        token_a_address=token_a_address,
        token_b_address=token_b_address,
        token_a_trade_amount=token_a_trade_amount,
        token_b_trade_amount=token_b_trade_amount,
    )

    # Final result
    print_header("Test Results")

    if success:
        print_success("ALL TESTS PASSED! ✓")
        print_info("\nTest Summary:")
        if use_env:
            print_info("  - Used pre-funded accounts from .env file")
            if use_predeployed_contract:
                print_info("  - Used pre-deployed contract (skipped compilation and deployment)")
            else:
                print_info("  - Compiled and deployed fresh contract")
        else:
            print_info("  - 3 fresh accounts generated")
            print_info("  - Accounts funded successfully")
            print_info("  - Compiled and deployed fresh contract")
        print_info(f"  - Contract address: {contract_address}")
        print_info(f"  - Order {order_id} created successfully")
        print_info(f"  - Order {order_id} filled successfully")
        print_info("  - Token A swapped for Token B successfully")
        print_info("  - All balance checks passed")
        return 0
    else:
        print_error("SOME TESTS FAILED! ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
