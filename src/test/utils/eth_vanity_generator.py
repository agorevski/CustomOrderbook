"""
Ethereum Vanity Address Generator Utility

A simple utility for generating random Ethereum addresses.
This is intended for testing and development purposes only.

WARNING: Do NOT use these addresses for production or real funds!
These are randomly generated and not derived from secure seed phrases.
"""

from eth_account import Account
from typing import Dict, List, Optional
import secrets


def generate_random_address() -> Dict[str, str]:
    """
    Generate a random Ethereum address with its private key.
    
    Returns:
        dict: A dictionary containing:
            - 'address': The Ethereum address (lowercase with 0x prefix)
            - 'checksum_address': The checksummed address (EIP-55 standard)
            - 'private_key': The private key as a hex string (with 0x prefix)
    
    Example:
        >>> result = generate_random_address()
        >>> print(f"Address: {result['address']}")
        >>> print(f"Private Key: {result['private_key']}")
    
    Security Warning:
        These addresses are randomly generated and should ONLY be used for:
        - Testing and development
        - Local blockchain networks
        - Test networks (Goerli, Sepolia, etc.)
        
        NEVER use these for production or real funds!
    """
    # Generate a random private key using secure random bytes
    private_key_bytes = secrets.token_bytes(32)
    
    # Create account from private key
    account = Account.from_key(private_key_bytes)
    
    return {
        'address': account.address.lower(),
        'checksum_address': account.address,
        'private_key': account.key.hex()
    }


def generate_multiple_addresses(count: int) -> List[Dict[str, str]]:
    """
    Generate multiple random Ethereum addresses.
    
    Args:
        count: Number of addresses to generate
    
    Returns:
        list: A list of dictionaries, each containing address and private key info
    
    Example:
        >>> addresses = generate_multiple_addresses(5)
        >>> for addr in addresses:
        ...     print(f"Address: {addr['address']}")
    """
    return [generate_random_address() for _ in range(count)]


def generate_vanity_address(
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    max_attempts: int = 10000,
    case_sensitive: bool = False
) -> Optional[Dict[str, str]]:
    """
    Generate an Ethereum address with a specific prefix or suffix pattern.
    
    Args:
        prefix: Desired prefix after '0x' (e.g., 'cafe' for 0xcafe...)
        suffix: Desired suffix (e.g., 'dead' for ...dead)
        max_attempts: Maximum number of attempts before giving up
        case_sensitive: Whether to match case exactly (default: False)
    
    Returns:
        dict: Address info if found within max_attempts, None otherwise
    
    Example:
        >>> # Find address starting with 0xabc
        >>> result = generate_vanity_address(prefix='abc', max_attempts=50000)
        >>> if result:
        ...     print(f"Found: {result['address']}")
        ... else:
        ...     print("No match found within attempt limit")
    
    Note:
        Finding specific patterns can take a long time. Each additional
        character in the pattern roughly multiplies search time by 16.
        Keep patterns short (1-4 characters) for reasonable performance.
    """
    if prefix:
        prefix = prefix.lower() if not case_sensitive else prefix
    if suffix:
        suffix = suffix.lower() if not case_sensitive else suffix
    
    for attempt in range(max_attempts):
        result = generate_random_address()
        address = result['address'][2:]  # Remove '0x' prefix
        
        if not case_sensitive:
            address = address.lower()
        
        # Check prefix match
        if prefix and not address.startswith(prefix):
            continue
        
        # Check suffix match
        if suffix and not address.endswith(suffix):
            continue
        
        # Found a match!
        return result
    
    # No match found within max_attempts
    return None


def generate_address_with_pattern(
    pattern: str,
    max_attempts: int = 10000
) -> Optional[Dict[str, str]]:
    """
    Generate an address containing a specific pattern anywhere in the address.
    
    Args:
        pattern: Pattern to search for (case-insensitive)
        max_attempts: Maximum number of attempts
    
    Returns:
        dict: Address info if found, None otherwise
    
    Example:
        >>> # Find address containing 'beef'
        >>> result = generate_address_with_pattern('beef', max_attempts=20000)
    """
    pattern = pattern.lower()
    
    for attempt in range(max_attempts):
        result = generate_random_address()
        address = result['address'][2:].lower()  # Remove '0x' and lowercase
        
        if pattern in address:
            return result
    
    return None


if __name__ == "__main__":
    # Demo usage
    print("=" * 70)
    print("Ethereum Vanity Address Generator - Demo")
    print("=" * 70)
    print()
    
    # Generate a single random address
    print("1. Generating a random address:")
    result = generate_random_address()
    print(f"   Address:          {result['address']}")
    print(f"   Checksum Address: {result['checksum_address']}")
    print(f"   Private Key:      {result['private_key']}")
    print()
    
    # Generate multiple addresses
    print("2. Generating 3 random addresses:")
    addresses = generate_multiple_addresses(3)
    for i, addr in enumerate(addresses, 1):
        print(f"   #{i}: {addr['checksum_address']}")
    print()
    
    # Try to find a vanity address with prefix
    print("3. Searching for address with prefix 'a' (should be fast):")
    vanity = generate_vanity_address(prefix='a', max_attempts=1000)
    if vanity:
        print(f"   Found: {vanity['checksum_address']}")
    else:
        print("   Not found within attempt limit")
    print()
    
    print("=" * 70)
    print("⚠️  WARNING: Use these addresses for testing ONLY!")
    print("    NEVER use for production or real funds!")
    print("=" * 70)
