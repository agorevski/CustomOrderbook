#!/usr/bin/env python3
"""
OrderBook Smart Contract Deployment Script
Deploys the OrderBook.sol contract to an EVM-compatible blockchain
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any
from web3 import Web3
from solcx import compile_standard, install_solc, set_solc_version
from eth_account import Account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OrderBookDeployer:
    """Handles deployment of OrderBook smart contract"""

    def __init__(self, network: str = "local"):
        """
        Initialize the deployer

        Args:
            network: Network name (local, sepolia, mumbai, polygon, ethereum)
        """
        self.network = network
        self.config = self._load_config(network)
        if not self.config:
            raise ValueError(f"Configuration for network '{network}' not found")
        self.w3 = self._setup_web3()
        self.account = self._setup_account()

    def _load_config(self, network: str) -> Dict[str, Any]:
        """Load network configuration from deployment_config.json.

        Args:
            network: The network name to load configuration for.

        Returns:
            Dictionary containing network configuration (rpc_url, chain_id, etc.).

        Raises:
            FileNotFoundError: If deployment_config.json is not found.
        """
        config_path = Path(__file__).parent / "deployment_config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                configs = json.load(f)
                return configs.get(network, None)
        else:
            raise FileNotFoundError("deployment_config.json not found")

    def _setup_web3(self) -> Web3:
        """Setup Web3 connection to the configured network.

        Returns:
            Web3 instance connected to the network.

        Raises:
            ConnectionError: If connection to the network fails.
        """
        rpc_url = self.config["rpc_url"]

        print(f"Connecting to {self.network} network...")
        print(f"RPC URL: {rpc_url}")

        w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not w3.is_connected():
            raise ConnectionError(
                f"Failed to connect to {self.network} network at {rpc_url}"
            )

        print(f"✓ Connected to network (Chain ID: {w3.eth.chain_id})")
        return w3

    def _setup_account(self) -> Account:
        """Setup deployer account from private key in environment variables.

        Returns:
            Account instance for the deployer.

        Raises:
            ValueError: If PRIVATE_KEY is not found in environment variables.
        """
        private_key = os.getenv("PRIVATE_KEY")

        if not private_key:
            raise ValueError(
                "PRIVATE_KEY not found in environment variables. "
                "Please set it in .env file or export it."
            )

        # Add 0x prefix if not present
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key

        account = Account.from_key(private_key)
        balance = self.w3.eth.get_balance(account.address)
        balance_eth = self.w3.from_wei(balance, "ether")

        print(f"✓ Deployer address: {account.address}")
        print(f"✓ Balance: {balance_eth} ETH")

        if balance == 0:
            print("⚠ WARNING: Account has zero balance. Deployment will fail.")

        return account

    def compile_contract(self, node_modules_dir: str) -> Dict[str, Any]:
        """Compile the OrderBook smart contract using solcx.

        Args:
            node_modules_dir: Path to node_modules directory containing OpenZeppelin contracts.

        Returns:
            Dictionary containing 'abi' and 'bytecode' of the compiled contract.

        Raises:
            FileNotFoundError: If OrderBook.sol or node_modules directory is not found.
        """
        print("\nCompiling OrderBook.sol...")

        # Install and set solc version
        solc_version = "0.8.20"
        print(f"Installing Solidity compiler version {solc_version}...")
        install_solc(solc_version)
        set_solc_version(solc_version)

        # Read contract source
        contract_path = Path(__file__).parent.parent / "contracts" / "OrderBook.sol"
        if not contract_path.exists():
            raise FileNotFoundError(
                "OrderBook.sol not found in src/contracts directory"
            )

        with open(contract_path, "r") as f:
            contract_source = f.read()

        # Get the project root directory (where node_modules is located)
        project_root = Path(__file__).parent.parent.parent
        node_modules_path = Path(node_modules_dir)

        # Check if node_modules exists in project root, otherwise check parent directory
        if not node_modules_path.exists():
            raise FileNotFoundError(
                "node_modules directory not found. Please run 'npm install @openzeppelin/contracts' "
                f"in either {project_root} or {project_root.parent}"
            )

        # Compile with import remapping
        compiled_sol = compile_standard(
            {
                "language": "Solidity",
                "sources": {"OrderBook.sol": {"content": contract_source}},
                "settings": {
                    "remappings": [
                        f"@openzeppelin/={node_modules_path}/@openzeppelin/"
                    ],
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

        print("✓ Contract compiled successfully")

        # Extract contract data
        contract_data = compiled_sol["contracts"]["OrderBook.sol"]["OrderBook"]

        return {
            "abi": contract_data["abi"],
            "bytecode": contract_data["evm"]["bytecode"]["object"],
        }

    def deploy_contract(self, contract_data: Dict[str, Any]) -> tuple:
        """Deploy the compiled contract to the blockchain.

        Args:
            contract_data: Dictionary containing 'abi' and 'bytecode' from compilation.

        Returns:
            Tuple of (contract_address, transaction_hash) for the deployed contract.

        Raises:
            Exception: If contract deployment transaction fails.
        """
        print("\nDeploying OrderBook contract...")

        # Create contract instance
        OrderBook = self.w3.eth.contract(
            abi=contract_data["abi"], bytecode=contract_data["bytecode"]
        )

        # Get nonce
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        # Estimate gas
        try:
            gas_estimate = OrderBook.constructor().estimate_gas(
                {"from": self.account.address}
            )
            print(f"✓ Estimated gas: {gas_estimate}")
        except Exception as e:
            print(f"⚠ Could not estimate gas: {e}")
            gas_estimate = self.config["gas_limit"]

        # Build transaction
        transaction = OrderBook.constructor().build_transaction(
            {
                "chainId": self.config["chain_id"],
                "gas": gas_estimate + 100000,  # Add buffer
                "gasPrice": self._get_gas_price(),
                "nonce": nonce,
                "from": self.account.address,
            }
        )

        # Sign transaction
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction, private_key=self.account.key
        )

        # Send transaction
        print("Sending deployment transaction...")
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        print(f"✓ Transaction sent: {tx_hash.hex()}")

        # Wait for receipt
        print("Waiting for confirmation...")
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if tx_receipt["status"] == 1:
            print("✓ Contract deployed successfully!")
            contract_address = tx_receipt["contractAddress"]
            print(f"✓ Contract address: {contract_address}")
            return contract_address, tx_hash.hex()
        else:
            raise Exception("Contract deployment failed")

    def _get_gas_price(self) -> int:
        """Get gas price for the deployment transaction.

        Returns:
            Gas price in wei. Uses network's current gas price if config is 'auto',
            otherwise uses the manually specified value from config.
        """
        if self.config["gas_price"] == "auto":
            gas_price = self.w3.eth.gas_price
            print(f"✓ Gas price (auto): {self.w3.from_wei(gas_price, 'gwei')} Gwei")
            return gas_price
        else:
            gas_price_gwei = int(self.config["gas_price"])
            gas_price = self.w3.to_wei(gas_price_gwei, "gwei")
            print(f"✓ Gas price (manual): {gas_price_gwei} Gwei")
            return gas_price

    def save_deployment_info(self, contract_address: str, tx_hash: str, abi: list):
        """Save deployment information to JSON files in the deployments directory.

        Args:
            contract_address: The deployed contract's address.
            tx_hash: The deployment transaction hash.
            abi: The contract's ABI as a list.
        """
        print("\nSaving deployment information...")

        # Create deployments directory
        deployments_dir = Path(__file__).parent.parent.parent / "deployments"
        deployments_dir.mkdir(exist_ok=True)

        # Save ABI
        abi_path = deployments_dir / "OrderBook_abi.json"
        with open(abi_path, "w") as f:
            json.dump(abi, f, indent=2)
        print(f"✓ ABI saved to {abi_path}")

        # Save deployment info
        deployment_info = {
            "network": self.network,
            "contract_address": contract_address,
            "transaction_hash": tx_hash,
            "deployer_address": self.account.address,
            "chain_id": self.config["chain_id"],
            "timestamp": self.w3.eth.get_block("latest")["timestamp"],
        }

        info_path = deployments_dir / f"OrderBook_{self.network}.json"
        with open(info_path, "w") as f:
            json.dump(deployment_info, f, indent=2)
        print(f"✓ Deployment info saved to {info_path}")

        # Save combined file for easy import
        combined_path = deployments_dir / f"OrderBook_{self.network}_complete.json"
        with open(combined_path, "w") as f:
            json.dump(
                {
                    "abi": abi,
                    "address": contract_address,
                    "network": self.network,
                    "transaction_hash": tx_hash,
                },
                f,
                indent=2,
            )
        print(f"✓ Complete deployment data saved to {combined_path}")

    def verify_deployment(self, contract_address: str, abi: list):
        """Verify the deployed contract by calling its functions.

        Args:
            contract_address: The deployed contract's address.
            abi: The contract's ABI as a list.

        Returns:
            Tuple of (success, owner_address, next_order_id, verification_status).
        """
        print("\nVerifying deployment...")

        contract = self.w3.eth.contract(address=contract_address, abi=abi)

        try:
            # Check owner
            owner = contract.functions.owner().call()
            print(f"✓ Contract owner: {owner}")

            # Check next order ID
            next_order_id = contract.functions.getNextOrderId().call()
            print(f"✓ Next order ID: {next_order_id}")

            # Verify owner matches deployer
            if owner.lower() == self.account.address.lower():
                print("✓ Owner verification successful")
                verification_status = "successful"
            else:
                print("⚠ WARNING: Owner does not match deployer")
                verification_status = "warning: owner mismatch"

            return True, owner, next_order_id, verification_status
        except Exception as e:
            print(f"✗ Verification failed: {e}")
            return False, None, None, "failed"

    def run(self, node_modules_dir: str):
        """Run the complete deployment process: compile, deploy, save, and verify.

        Args:
            node_modules_dir: Path to node_modules directory containing OpenZeppelin contracts.
        """
        print("=" * 70)
        print("OrderBook Smart Contract Deployment")
        print("=" * 70)

        try:
            # Compile
            contract_data = self.compile_contract(node_modules_dir)

            # Deploy
            contract_address, tx_hash = self.deploy_contract(contract_data)

            # Save info
            self.save_deployment_info(contract_address, tx_hash, contract_data["abi"])

            # Verify
            verification_success, owner, next_order_id, verification_status = (
                self.verify_deployment(contract_address, contract_data["abi"])
            )

            print("\n" + "=" * 70)
            print("DEPLOYMENT SUCCESSFUL!")
            print("=" * 70)
            print(f"Network: {self.network}")
            print(f"Contract Address: {contract_address}")
            print(f"Transaction Hash: {tx_hash}")
            print(f"Explorer URL: {self._get_explorer_url(contract_address)}")
            print("=" * 70)

        except Exception as e:
            print("\n" + "=" * 70)
            print("DEPLOYMENT FAILED!")
            print("=" * 70)
            print(f"Error: {str(e)}")
            print("=" * 70)
            sys.exit(1)

    def _get_explorer_url(self, contract_address: str) -> str:
        """Get block explorer URL for the deployed contract.

        Args:
            contract_address: The deployed contract's address.

        Returns:
            URL string to view the contract on the network's block explorer.
        """
        explorers = {
            "ethereum": f"https://etherscan.io/address/{contract_address}",
            "sepolia": f"https://sepolia.etherscan.io/address/{contract_address}",
            "polygon": f"https://polygonscan.com/address/{contract_address}",
            "mumbai": f"https://mumbai.polygonscan.com/address/{contract_address}",
            "local": "N/A (Local network)",
        }
        return explorers.get(self.network, "N/A")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for the deployment script.

    Returns:
        Namespace containing parsed arguments (network, node_modules_dir).
    """
    parser = argparse.ArgumentParser(description="Deploy OrderBook smart contract")
    parser.add_argument(
        "--network",
        type=str,
        default="tenderly",
        help="Network to deploy to (default: tenderly)",
    )
    parser.add_argument(
        "--node-modules-dir",
        type=str,
        default="C:\\GIT\\node_modules",
        help="Path to node_modules directory (if needed)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    deployer = OrderBookDeployer(network=args.network)
    deployer.run(args.node_modules_dir)
