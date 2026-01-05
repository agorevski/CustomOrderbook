#!/usr/bin/env python3
"""
Fund Test Wallets Utility

This script funds test wallets on Tenderly virtual testnet with:
1. Native balance (ETH) for gas fees
2. ERC-20 token balances as specified in test_wallets.json

The script dynamically queries token decimals from the smart contracts
and calculates the proper amounts to fund.
"""

import json
import sys
import os
import requests
from web3 import Web3


# ANSI color codes for console output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_success(message):
    """Print success message in green.

    Args:
        message: The message to display with a green checkmark prefix.
    """
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message):
    """Print error message in red.

    Args:
        message: The message to display with a red X prefix.
    """
    print(f"{Colors.RED}✗{Colors.RESET} {message}")


def print_info(message):
    """Print info message in cyan.

    Args:
        message: The message to display with a cyan info prefix.
    """
    print(f"{Colors.CYAN}ℹ{Colors.RESET} {message}")


def print_header(message):
    """Print header message with bold formatting and separator lines.

    Args:
        message: The header text to display, centered within an 80-character width.
    """
    print(f"\n{Colors.BOLD}{'='*80}")
    print(f"{message:^80}")
    print(f"{'='*80}{Colors.RESET}\n")


def load_json_file(file_path, description):
    """Load and parse a JSON file.

    Args:
        file_path: The path to the JSON file to load.
        description: A human-readable description of the file for logging purposes.

    Returns:
        The parsed JSON data as a Python object (dict or list).

    Raises:
        SystemExit: If the file is not found or contains invalid JSON.
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        print_success(f"Loaded {description}")
        return data
    except FileNotFoundError:
        print_error(f"File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {file_path}: {e}")
        sys.exit(1)


def get_token_decimals(w3, token_address):
    """Query the decimals from an ERC-20 token contract.

    Args:
        w3: A connected Web3 instance for making contract calls.
        token_address: The address of the ERC-20 token contract.

    Returns:
        The number of decimals for the token (typically 18 for most tokens).

    Raises:
        SystemExit: If the contract call fails or the token doesn't implement decimals().
    """
    # Standard ERC-20 decimals() function ABI
    decimals_abi = [
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function",
        }
    ]

    try:
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=decimals_abi
        )
        decimals = token_contract.functions.decimals().call()
        return decimals
    except Exception as e:
        print_error(f"Failed to get decimals for token {token_address}: {e}")
        sys.exit(1)


def tenderly_rpc_call(rpc_url, method, params):
    """Make a JSON-RPC call to Tenderly.

    Args:
        rpc_url: The Tenderly RPC endpoint URL.
        method: The JSON-RPC method name to call (e.g., 'tenderly_setBalance').
        params: A list of parameters to pass to the RPC method.

    Returns:
        The result field from the JSON-RPC response.

    Raises:
        SystemExit: If the request fails or the RPC returns an error.
    """
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


def fund_native_balance(rpc_url, addresses, amount_wei):
    """Fund native balance (ETH) to addresses using tenderly_setBalance.

    Args:
        rpc_url: The Tenderly RPC endpoint URL.
        addresses: A list of wallet addresses to fund.
        amount_wei: The amount of ETH to fund in Wei.

    Returns:
        The result from the Tenderly RPC call.
    """
    print_info(
        f"Funding {len(addresses)} address(es) with {Web3.from_wei(amount_wei, 'ether')} ETH each..."
    )

    amount_hex = hex(amount_wei)

    result = tenderly_rpc_call(rpc_url, "tenderly_setBalance", [addresses, amount_hex])

    print_success(f"Native balance funded: {', '.join(addresses)}")
    return result


def fund_erc20_balance(rpc_url, token_address, addresses, amount):
    """Fund ERC-20 token balance using tenderly_setErc20Balance.

    Args:
        rpc_url: The Tenderly RPC endpoint URL.
        token_address: The address of the ERC-20 token contract.
        addresses: A list of wallet addresses to fund.
        amount: The amount of tokens to fund (including decimals).

    Returns:
        The result from the Tenderly RPC call.
    """
    print_info(
        f"Funding {len(addresses)} address(es) with {amount} tokens from {token_address}..."
    )

    amount_hex = hex(amount)

    result = tenderly_rpc_call(
        rpc_url, "tenderly_setErc20Balance", [token_address, addresses, amount_hex]
    )

    print_success(f"ERC-20 balance funded: {token_address} -> {', '.join(addresses)}")
    return result


def main():
    """Main execution function for funding test wallets.

    Loads configuration files, connects to Web3, and funds both native ETH
    and ERC-20 token balances for the ask and fill test wallets on the
    Tenderly virtual testnet.

    Raises:
        SystemExit: If configuration loading fails or Web3 connection fails.
    """
    print_header("Fund Test Wallets Utility")

    # Determine base paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, "..", "..")

    # Load configuration files
    print_info("Loading configuration files...")

    wallets_path = os.path.join(script_dir, "test_wallets.json")
    wallets = load_json_file(wallets_path, "test_wallets.json")

    config_path = os.path.join(script_dir, "..", "deploy", "deployment_config.json")
    config = load_json_file(config_path, "deployment_config.json")

    # Get RPC URL
    rpc_url = config.get("tenderly", {}).get("rpc_url")
    if not rpc_url:
        print_error("RPC URL not found in deployment_config.json")
        sys.exit(1)

    print_success(f"Using RPC: {rpc_url}")

    # Initialize Web3 for querying token decimals
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print_error("Failed to connect to Web3 provider")
        sys.exit(1)

    print_success("Connected to Web3 provider")

    # Fund native balance (1 ETH) for both wallets
    print_header("Funding Native Balance (ETH)")

    addresses_to_fund = [
        wallets["ask_wallet"]["address"],
        wallets["fill_wallet"]["address"],
    ]

    # 1 ETH in Wei
    one_eth_wei = Web3.to_wei(1, "ether")

    fund_native_balance(rpc_url, addresses_to_fund, one_eth_wei)

    # Fund ERC-20 tokens for ask_wallet
    print_header("Funding Ask Wallet ERC-20 Tokens")

    ask_wallet = wallets["ask_wallet"]
    ask_token_address = ask_wallet["have_address"]
    ask_amount_base = ask_wallet["have_amount"]

    print_info(f"Querying decimals for token: {ask_token_address}")
    ask_decimals = get_token_decimals(w3, ask_token_address)
    print_success(f"Token decimals: {ask_decimals}")

    ask_amount_with_decimals = ask_amount_base * (10**ask_decimals)
    print_info(
        f"Amount to fund: {ask_amount_base} tokens = {ask_amount_with_decimals} (with decimals)"
    )

    fund_erc20_balance(
        rpc_url, ask_token_address, [ask_wallet["address"]], ask_amount_with_decimals
    )

    # Fund ERC-20 tokens for fill_wallet
    print_header("Funding Fill Wallet ERC-20 Tokens")

    fill_wallet = wallets["fill_wallet"]
    fill_token_address = fill_wallet["have_address"]
    fill_amount_base = fill_wallet["have_amount"]

    print_info(f"Querying decimals for token: {fill_token_address}")
    fill_decimals = get_token_decimals(w3, fill_token_address)
    print_success(f"Token decimals: {fill_decimals}")

    fill_amount_with_decimals = fill_amount_base * (10**fill_decimals)
    print_info(
        f"Amount to fund: {fill_amount_base} tokens = {fill_amount_with_decimals} (with decimals)"
    )

    fund_erc20_balance(
        rpc_url, fill_token_address, [fill_wallet["address"]], fill_amount_with_decimals
    )

    # Summary
    print_header("Funding Complete")
    print_success("All wallets funded successfully!")
    print_info("\nFunding Summary:")
    print_info(f"  Ask Wallet ({ask_wallet['address']}):")
    print_info(f"    - Native: 1 ETH")
    print_info(f"    - Token: {ask_amount_base} units of {ask_token_address}")
    print_info(f"  Fill Wallet ({fill_wallet['address']}):")
    print_info(f"    - Native: 1 ETH")
    print_info(f"    - Token: {fill_amount_base} units of {fill_token_address}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        sys.exit(1)
