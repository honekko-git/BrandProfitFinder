"""
Authentication normalization for used luxury items.
"""

from models.authentication_info import AuthenticationInfo, AuthenticationStatus


class AuthenticationNormalizer:
    """Normalize authentication data without over-crediting seller claims."""

    def normalize(self, raw: dict[str, object] | None) -> AuthenticationInfo:
        """
        Build authentication info from raw data.

        Args:
            raw: Raw authentication dictionary.

        Returns:
            Normalized AuthenticationInfo with warnings when appropriate.
        """
        info = AuthenticationInfo()
        if not raw:
            return info

        info.status = AuthenticationStatus.from_value(raw.get("status"))
        info.provider = str(raw.get("provider") or "").strip()
        info.method = str(raw.get("method") or "").strip()
        info.certificate_number = str(raw.get("certificate_number") or "").strip()
        info.notes = str(raw.get("notes") or "").strip()
        info.authentication_date = str(raw.get("authentication_date") or "").strip()

        info.authenticity_guarantee = _optional_bool(raw.get("authenticity_guarantee"))
        info.seller_claimed_authentic = _optional_bool(raw.get("seller_claimed_authentic"))
        info.platform_authenticated = _optional_bool(raw.get("platform_authenticated"))
        info.third_party_authenticated = _optional_bool(raw.get("third_party_authenticated"))

        info = self._resolve_status(info)
        return info

    def _resolve_status(self, info: AuthenticationInfo) -> AuthenticationInfo:
        """
        Resolve final status from flags without treating seller claims as authentication.

        Args:
            info: Partially filled authentication info.

        Returns:
            Updated info with resolved status and warnings.
        """
        warnings = list(info.warnings)

        if info.status == AuthenticationStatus.UNKNOWN:
            if info.third_party_authenticated is True:
                info.status = AuthenticationStatus.THIRD_PARTY_REVIEWED
            elif info.platform_authenticated is True:
                info.status = AuthenticationStatus.PLATFORM_REVIEWED
            elif info.seller_claimed_authentic is True:
                info.status = AuthenticationStatus.SELLER_CLAIM_ONLY
                warnings.append("seller claim only; not treated as authenticated")

        if info.status == AuthenticationStatus.AUTHENTICATED:
            if not info.platform_authenticated and not info.third_party_authenticated:
                if info.seller_claimed_authentic:
                    info.status = AuthenticationStatus.SELLER_CLAIM_ONLY
                    warnings.append("authenticated status downgraded to seller claim only")

        if info.status == AuthenticationStatus.SELLER_CLAIM_ONLY:
            warnings.append("seller claim is not equivalent to third-party authentication")

        info.warnings = warnings
        return info


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None
