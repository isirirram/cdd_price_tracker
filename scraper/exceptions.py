"""
Domain exceptions for the Smart Price Tracker Scraper module.

All scraper exceptions inherit from ScraperException for unified error handling.
"""


class ScraperException(Exception):
    """Base exception for all scraper-related errors."""
    def __init__(self, message: str, site: str = "unknown"):
        self.message = message
        self.site = site
        super().__init__(self.message)


class InvalidUrlError(ScraperException):
    """Raised when an input URL is malformed or invalid."""
    pass


class UnsupportedWebsiteError(ScraperException):
    """Raised when a URL belongs to a domain not recognized by any registered adapter."""
    pass


class ApiCredentialsMissingError(ScraperException):
    """Raised when required API credentials (keys, tokens, tags) are not configured."""
    pass


class RegistrationGatedError(ScraperException):
    """Raised when an official API requires account approval or sales velocity not currently met."""
    pass


class PolicyRestrictedWebsiteError(ScraperException):
    """Raised when a website's Terms of Use explicitly forbid automated scrapers or bots."""
    pass


class NetworkTimeoutError(ScraperException):
    """Raised when an external API or network request exceeds the timeout threshold."""
    pass


class ProductNotFoundError(ScraperException):
    """Raised when a product or barcode cannot be found on the target platform."""
    pass


class PriceNotFoundError(ScraperException):
    """Raised when product details exist but no current valid price can be extracted."""
    pass

