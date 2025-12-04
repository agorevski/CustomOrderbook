"""
Example usage of the eth_vanity_generator utility module.

This demonstrates how to import and use the utility functions
in your own Python scripts.
"""

from eth_vanity_generator import (
    generate_random_address,
    generate_multiple_addresses,
    generate_vanity_address,
    generate_address_with_pattern
)

def example_basic_usage():
    """Example: Generate a single random address."""
    print("\n--- Example 1: Basic Usage ---")
    result = generate_random_address()
    print(f"Generated Address: {result['checksum_address']}")
    print(f"Private Key: {result['private_key']}")

def example_batch_generation():
    """Example: Generate multiple addresses at once."""
    print("\n--- Example 2: Batch Generation ---")
    addresses = generate_multiple_addresses(5)
    print("Generated 5 addresses:")
    for i, addr in enumerate(addresses, 1):
        print(f"  {i}. {addr['checksum_address']}")

def example_vanity_prefix():
    """Example: Generate address with specific prefix."""
    print("\n--- Example 3: Vanity Address (Prefix) ---")
    print("Searching for address starting with 0xabc...")
    result = generate_vanity_address(prefix='abc', max_attempts=50000)
    if result:
        print(f"✓ Found: {result['checksum_address']}")
        print(f"  Private Key: {result['private_key']}")
    else:
        print("✗ No match found within attempt limit")

def example_vanity_suffix():
    """Example: Generate address with specific suffix."""
    print("\n--- Example 4: Vanity Address (Suffix) ---")
    print("Searching for address ending with 'cafe'...")
    result = generate_vanity_address(suffix='cafe', max_attempts=50000)
    if result:
        print(f"✓ Found: {result['checksum_address']}")
    else:
        print("✗ No match found within attempt limit")

def example_pattern_matching():
    """Example: Generate address containing a pattern."""
    print("\n--- Example 5: Pattern Matching ---")
    print("Searching for address containing '1234'...")
