#!/usr/bin/env python3
"""
OrderBook Contract Integrated Test Script

This script provides a complete test lifecycle:
1. Generate 3 brand new vanity accounts
2. Fund the accounts with ETH and tokens
3. Deploy OrderBook.sol contract to Tenderly
4. Run comprehensive tests on the deployed contract

Usage:
    python test_orderbook.py
"""

import json
import sys
import os
import requests
from pathlib import Path
from web3 import Web3
from eth_account import Account
from decimal import Decimal
from solcx import compile_standard, install_solc, set_solc_version

# Add utils directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "utils"))
from eth_vanity_generator import generate_multiple_addresses

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

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

def load_json_file(filepath):
    """Load and parse JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print_error(f"File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {filepath}: {e}")
        sys.exit(1)

def format_token_amount(amount, decimals=6):
    """Format token amount with decimals"""
    return float(amount) / (10 ** decimals)

def to_wei_custom(amount, decimals=6):
    """Convert amount to smallest unit based on token decimals"""
    return int(amount * (10 ** decimals))

def tenderly_rpc_call(rpc_url, method, params):
    """Make a JSON-RPC call to Tenderly"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": "1"
    }
    
    try:
        response = requests.post(
            rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"}
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
    print_success(f"Ask Account: {ask_account['checksum_address']}")
    print_success(f"Fill Account: {fill_account['checksum_address']}")
    
    return deployment_account, ask_account, fill_account

def fund_accounts(rpc_url, deployment_account, ask_account, fill_account):
    """Fund accounts with ETH and tokens via Tenderly RPC"""
    print_header("Funding Test Accounts")
    
    # Token addresses
    USDC_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    TOKEN_B_ADDRESS = "0x2433D6AC11193b4695D9ca73530de93c538aD18a"
    
    # Fund native balance (10 ETH each)
    print_info("Funding native balance (10 ETH each)...")
    eth_amount = Web3.to_wei(10, 'ether')
    eth_amount_hex = hex(eth_amount)
    
    addresses_to_fund = [
        deployment_account['checksum_address'],
        ask_account['checksum_address'],
        fill_account['checksum_address']
    ]
    
    tenderly_rpc_call(rpc_url, "tenderly_setBalance", [addresses_to_fund, eth_amount_hex])
    print_success("Native balance funded for all accounts")
    
    # Fund Ask Account with 100 USDC (6 decimals)
    print_info("Funding Ask Account with 100 USDC...")
    usdc_amount = 100 * (10 ** 6)
    usdc_amount_hex = hex(usdc_amount)
    
    tenderly_rpc_call(
        rpc_url,
        "tenderly_setErc20Balance",
        [USDC_ADDRESS, [ask_account['checksum_address']], usdc_amount_hex]
    )
    print_success(f"Ask Account funded with 100 USDC")
    
    # Fund Fill Account with 50,000 Token B (6 decimals)
    print_info("Funding Fill Account with 50,000 Token B...")
    token_b_amount = 50000 * (10 ** 6)
    token_b_amount_hex = hex(token_b_amount)
    
    tenderly_rpc_call(
        rpc_url,
        "tenderly_setErc20Balance",
        [TOKEN_B_ADDRESS, [fill_account['checksum_address']], token_b_amount_hex]
    )
    print_success(f"Fill Account funded with 50,000 Token B")
    
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
    
    with open(contract_path, 'r') as f:
        contract_source = f.read()
    
    print_info("Locating node_modules for OpenZeppelin imports...")
    
    # Try to find node_modules
    project_root = Path(__file__).parent.parent.parent
    possible_paths = [
        project_root / "node_modules",
        project_root.parent / "node_modules",
        Path("C:/GIT/node_modules")
    ]
    
    node_modules_path = None
    for path in possible_paths:
        if path.exists():
            node_modules_path = path
            break
    
    if not node_modules_path:
        print_error("node_modules directory not found. Please run 'npm install @openzeppelin/contracts'")
        sys.exit(1)
    
    print_success(f"Found node_modules at: {node_modules_path}")
    
    print_info("Compiling contract...")
    
    # Compile with import remapping
    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {
                "OrderBook.sol": {
                    "content": contract_source
                }
            },
            "settings": {
                "remappings": [
                    f"@openzeppelin/={node_modules_path}/@openzeppelin/"
                ],
                "optimizer": {
                    "enabled": True,
                    "runs": 200
                },
                "outputSelection": {
                    "*": {
                        "*": [
                            "abi",
                            "metadata",
                            "evm.bytecode",
                            "evm.bytecode.sourceMap"
                        ]
                    }
                }
            }
        },
        allow_paths=[str(project_root), str(node_modules_path)]
    )
    
    print_success("Contract compiled successfully")
    
    # Extract contract data
    contract_data = compiled_sol['contracts']['OrderBook.sol']['OrderBook']
    
    return {
        'abi': contract_data['abi'],
        'bytecode': contract_data['evm']['bytecode']['object']
    }

def deploy_orderbook_contract(w3, deployment_account, contract_data):
    """Deploy the OrderBook contract using the deployment account"""
    print_header("Deploying OrderBook Contract")
    
    # Create contract instance
    OrderBook = w3.eth.contract(
        abi=contract_data['abi'],
        bytecode=contract_data['bytecode']
    )
    
    # Get deployer account
    deployer_address = deployment_account['checksum_address']
    deployer_key = deployment_account['private_key']
    
    # Get nonce
    nonce = w3.eth.get_transaction_count(deployer_address)
    
    print_info(f"Deploying from: {deployer_address}")
    
    # Estimate gas
    try:
        gas_estimate = OrderBook.constructor().estimate_gas({
            'from': deployer_address
        })
        print_success(f"Estimated gas: {gas_estimate}")
    except Exception as e:
        print_warning(f"Could not estimate gas: {e}")
        gas_estimate = 3000000
    
    # Build transaction
    transaction = OrderBook.constructor().build_transaction({
        'chainId': w3.eth.chain_id,
        'gas': gas_estimate + 100000,  # Add buffer
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
        'from': deployer_address
    })
    
    # Sign transaction
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=deployer_key)
    
    # Send transaction
    print_info("Sending deployment transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print_success(f"Transaction sent: {tx_hash.hex()}")
    
    # Wait for receipt
    print_info("Waiting for confirmation...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    if tx_receipt['status'] == 1:
        contract_address = tx_receipt['contractAddress']
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
            "type": "function"
        }
    ]
    
    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=erc20_abi
    )
    
    balance = token_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet_address)
    ).call()
    
    return balance

def approve_token(w3, token_address, spender_address, amount, private_key, from_address):
    """Approve token spending"""
    # Minimal ERC20 ABI for approve
    erc20_abi = [
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }
    ]
    
    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=erc20_abi
    )
    
    # Build transaction
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))
    
    tx = token_contract.functions.approve(
        Web3.to_checksum_address(spender_address),
        amount
    ).build_transaction({
        'from': Web3.to_checksum_address(from_address),
        'nonce': nonce,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price
    })
    
    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    return receipt

def create_order(w3, contract, offered_token, offered_amount, requested_token, 
                requested_amount, private_key, from_address):
    """Create an order on the OrderBook"""
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))
    
    tx = contract.functions.createOrder(
        Web3.to_checksum_address(offered_token),
        offered_amount,
        Web3.to_checksum_address(requested_token),
        requested_amount
    ).build_transaction({
        'from': Web3.to_checksum_address(from_address),
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })
    
    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    return receipt

def fill_order(w3, contract, order_id, private_key, from_address):
    """Fill an order on the OrderBook"""
    nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))
    
    tx = contract.functions.fillOrder(order_id).build_transaction({
        'from': Web3.to_checksum_address(from_address),
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })
    
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
        return logs[0]['args']['orderId']
    return None

def run_orderbook_tests(w3, contract_address, contract_abi, ask_account, fill_account):
    """Run the OrderBook tests"""
    print_header("Running OrderBook Tests")
    
    # Token addresses (USDC has 6 decimals, Token B has 6 decimals)
    USDC_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    TOKEN_B_ADDRESS = "0x2433D6AC11193b4695D9ca73530de93c538aD18a"
    
    # Initialize contract
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=contract_abi
    )
    
    # Extract wallet info
    ask_address = ask_account['checksum_address']
    fill_address = fill_account['checksum_address']
    
    ask_private_key = ask_account['private_key']
    fill_private_key = fill_account['private_key']
    
    # Expected amounts
    ask_offered_amount = to_wei_custom(100, 6)  # 100 USDC
    ask_requested_amount = to_wei_custom(50000, 6)  # 50000 Token B
    
    # Step 1: Verify pre-conditions
    print_header("Step 1: Verifying Pre-conditions")
    
    print_info("Checking ask_wallet balances...")
    ask_usdc_balance = get_token_balance(w3, USDC_ADDRESS, ask_address)
    ask_tokenb_balance = get_token_balance(w3, TOKEN_B_ADDRESS, ask_address)
    
    print_info(f"  Ask Account ({ask_address}):")
    print_info(f"    USDC Balance: {format_token_amount(ask_usdc_balance, 6)}")
    print_info(f"    Token B Balance: {format_token_amount(ask_tokenb_balance, 6)}")
    
    if ask_usdc_balance < ask_offered_amount:
        print_error(f"Ask account has insufficient USDC balance. Has {format_token_amount(ask_usdc_balance, 6)}, needs 100")
        sys.exit(1)
    
    print_success(f"Ask account has sufficient USDC: {format_token_amount(ask_usdc_balance, 6)}")
    
    print_info("\nChecking fill_wallet balances...")
    fill_usdc_balance = get_token_balance(w3, USDC_ADDRESS, fill_address)
    fill_tokenb_balance = get_token_balance(w3, TOKEN_B_ADDRESS, fill_address)
    
    print_info(f"  Fill Account ({fill_address}):")
    print_info(f"    USDC Balance: {format_token_amount(fill_usdc_balance, 6)}")
    print_info(f"    Token B Balance: {format_token_amount(fill_tokenb_balance, 6)}")
    
    if fill_tokenb_balance < ask_requested_amount:
        print_error(f"Fill account has insufficient Token B balance. Has {format_token_amount(fill_tokenb_balance, 6)}, needs 50000")
        sys.exit(1)
    
    print_success(f"Fill account has sufficient Token B: {format_token_amount(fill_tokenb_balance, 6)}")
    
    # Step 2: Approve and create order
    print_header("Step 2: Creating Order from Ask Account")
    
    print_info(f"Approving OrderBook to spend 100 USDC from ask_account...")
    
    try:
        approve_receipt = approve_token(
            w3, USDC_ADDRESS, contract_address, 
            ask_offered_amount, ask_private_key, ask_address
        )
        print_success(f"Approval transaction successful: {approve_receipt['transactionHash'].hex()}")
        print_info(f"  Gas used: {approve_receipt['gasUsed']}")
    except Exception as e:
        print_error(f"Approval failed: {e}")
        sys.exit(1)
    
    print_info(f"\nCreating order: 100 USDC for 50000 Token B...")
    
    try:
        create_receipt = create_order(
            w3, contract, USDC_ADDRESS, ask_offered_amount,
            TOKEN_B_ADDRESS, ask_requested_amount,
            ask_private_key, ask_address
        )
        print_success(f"Order created successfully: {create_receipt['transactionHash'].hex()}")
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
    
    print_info(f"Approving OrderBook to spend 50000 Token B from fill_account...")
    
    try:
        approve_receipt = approve_token(
            w3, TOKEN_B_ADDRESS, contract_address,
            ask_requested_amount, fill_private_key, fill_address
        )
        print_success(f"Approval transaction successful: {approve_receipt['transactionHash'].hex()}")
        print_info(f"  Gas used: {approve_receipt['gasUsed']}")
    except Exception as e:
        print_error(f"Approval failed: {e}")
        sys.exit(1)
    
    print_info(f"\nFilling order {order_id}...")
    
    try:
        fill_receipt = fill_order(w3, contract, order_id, fill_private_key, fill_address)
        print_success(f"Order filled successfully: {fill_receipt['transactionHash'].hex()}")
        print_info(f"  Gas used: {fill_receipt['gasUsed']}")
    except Exception as e:
        print_error(f"Order fill failed: {e}")
        sys.exit(1)
    
    # Step 4: Verify post-conditions
    print_header("Step 4: Verifying Post-conditions")
    
    print_info("Checking final balances...")
    
    # Ask account final balances
    ask_usdc_final = get_token_balance(w3, USDC_ADDRESS, ask_address)
    ask_tokenb_final = get_token_balance(w3, TOKEN_B_ADDRESS, ask_address)
    
    print_info(f"\nAsk Account ({ask_address}):")
    print_info(f"  USDC: {format_token_amount(ask_usdc_balance, 6)} → {format_token_amount(ask_usdc_final, 6)}")
    print_info(f"  Token B: {format_token_amount(ask_tokenb_balance, 6)} → {format_token_amount(ask_tokenb_final, 6)}")
    
    # Fill account final balances
    fill_usdc_final = get_token_balance(w3, USDC_ADDRESS, fill_address)
    fill_tokenb_final = get_token_balance(w3, TOKEN_B_ADDRESS, fill_address)
    
    print_info(f"\nFill Account ({fill_address}):")
    print_info(f"  USDC: {format_token_amount(fill_usdc_balance, 6)} → {format_token_amount(fill_usdc_final, 6)}")
    print_info(f"  Token B: {format_token_amount(fill_tokenb_balance, 6)} → {format_token_amount(fill_tokenb_final, 6)}")
    
    # Verify the swap was successful
    print_info("\nVerifying swap results...")
    
    success = True
    
    # Ask account should have received Token B and lost USDC
    expected_ask_usdc = ask_usdc_balance - ask_offered_amount
    expected_ask_tokenb = ask_tokenb_balance + ask_requested_amount
    
    if ask_usdc_final == expected_ask_usdc:
        print_success(f"Ask account USDC balance correct: {format_token_amount(ask_usdc_final, 6)}")
    else:
        print_error(f"Ask account USDC balance incorrect. Expected {format_token_amount(expected_ask_usdc, 6)}, got {format_token_amount(ask_usdc_final, 6)}")
        success = False
    
    if ask_tokenb_final == expected_ask_tokenb:
        print_success(f"Ask account Token B balance correct: {format_token_amount(ask_tokenb_final, 6)}")
    else:
        print_error(f"Ask account Token B balance incorrect. Expected {format_token_amount(expected_ask_tokenb, 6)}, got {format_token_amount(ask_tokenb_final, 6)}")
        success = False
    
    # Fill account should have received USDC and lost Token B
    expected_fill_usdc = fill_usdc_balance + ask_offered_amount
    expected_fill_tokenb = fill_tokenb_balance - ask_requested_amount
    
    if fill_usdc_final == expected_fill_usdc:
        print_success(f"Fill account USDC balance correct: {format_token_amount(fill_usdc_final, 6)}")
    else:
        print_error(f"Fill account USDC balance incorrect. Expected {format_token_amount(expected_fill_usdc, 6)}, got {format_token_amount(fill_usdc_final, 6)}")
        success = False
    
    if fill_tokenb_final == expected_fill_tokenb:
        print_success(f"Fill account Token B balance correct: {format_token_amount(fill_tokenb_final, 6)}")
    else:
        print_error(f"Fill account Token B balance incorrect. Expected {format_token_amount(expected_fill_tokenb, 6)}, got {format_token_amount(fill_tokenb_final, 6)}")
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

def main():
    """Main test execution"""
    print_header("OrderBook Contract - Integrated Test Suite")
    print_info("This test will generate fresh accounts, deploy a new contract, and run tests")
    
    # Load network configuration
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "src" / "deploy" / "deployment_config.json"
    network_config = load_json_file(config_path)
    
    rpc_url = network_config['tenderly']['rpc_url']
    print_success(f"RPC URL: {rpc_url}")
    
    # Connect to blockchain
    print_info("\nConnecting to Tenderly network...")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        print_error("Failed to connect to network")
        sys.exit(1)
    
    print_success(f"Connected to chain ID: {w3.eth.chain_id}")
    
    # Phase 1: Compile contract
    print_header("Phase 1: Compile Contract")
    contract_data = compile_orderbook_contract()

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
        contract_data['abi'], 
        ask_account, 
        fill_account
    )
    
    # Final result
    print_header("Test Results")
    
    if success:
        print_success("ALL TESTS PASSED! ✓")
        print_info("\nTest Summary:")
        print_info(f"  - 3 fresh accounts generated")
        print_info(f"  - Accounts funded successfully")
        print_info(f"  - Contract deployed at: {contract_address}")
        print_info(f"  - Order {order_id} created successfully")
        print_info(f"  - Order {order_id} filled successfully")
        print_info(f"  - 100 USDC swapped for 50000 Token B")
        print_info(f"  - All balance checks passed")
        return 0
    else:
        print_error("SOME TESTS FAILED! ✗")
        return 1

if __name__ == "__main__":
    sys.exit(main())
