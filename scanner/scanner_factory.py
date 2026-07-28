"""
Scanner factory for creating store scanner instances.
"""

from config.constants import STORE_BALTINI, STORE_CETTIRE, STORE_ITALIST
from scanner.base_scanner import BaseScanner
from scanner.baltini import BaltiniScanner
from scanner.cettire import CettireScanner


def create_scanner(store_name: str) -> BaseScanner:
    """
    Create a scanner instance for the given store name.

    Args:
        store_name: Store identifier (case-insensitive).

    Returns:
        Configured scanner instance.

    Raises:
        ValueError: When store name is not supported.
    """
    normalized = store_name.strip().lower()
    registry: dict[str, type[BaseScanner]] = {
        STORE_CETTIRE.lower(): CettireScanner,
        STORE_BALTINI.lower(): BaltiniScanner,
    }

    scanner_class = registry.get(normalized)
    if scanner_class is None:
        if normalized == STORE_ITALIST.lower():
            raise ValueError("Italist scanner is not yet implemented")
        raise ValueError(f"Unsupported store: {store_name}")

    return scanner_class()


def get_all_scanners() -> list[BaseScanner]:
    """
    Return scanner instances for all implemented stores.

    Returns:
        List of scanner instances.
    """
    return [CettireScanner(), BaltiniScanner()]
