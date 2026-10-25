"""Authorization is decided here, in code. The LLM never decides who may see what."""

from app.core.security import ALL_PRODUCTS, Principal


class AccessPolicy:
    def can_access_product(self, principal: Principal, product: str) -> bool:
        return ALL_PRODUCTS in principal.products or product in principal.products

    def allowed_products(self, principal: Principal) -> frozenset[str]:
        """Passed to search so filtering happens before content is returned."""
        return principal.products
