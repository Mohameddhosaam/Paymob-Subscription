"""
HMAC verification for Paymob's transaction/token webhook callbacks.

If you already have a working hmac_utils.py from before, keep using that one —
this is only a reference implementation in case you need to recreate it.
Field orders below are Paymob's documented, standard lists for the classic
Accept transaction/token callbacks.
"""
import hashlib
import hmac as hmac_lib

TRANSACTION_FIELD_ORDER = [
    "amount_cents", "created_at", "currency", "error_occured",
    "has_parent_transaction", "id", "integration_id", "is_3d_secure",
    "is_auth", "is_capture", "is_refunded", "is_standalone_payment",
    "is_voided", "order.id" if False else "order", "owner", "pending",
    "source_data.pan", "source_data.sub_type", "source_data.type", "success",
]

TOKEN_FIELD_ORDER = [
    "card_subtype", "created_at", "email", "id", "masked_pan",
    "merchant_id", "order_id", "token",
]


def _get_nested(obj: dict, dotted_key: str):
    value = obj
    for part in dotted_key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def concatenated_string(obj: dict, field_order: list) -> str:
    parts = []
    for key in field_order:
        value = _get_nested(obj, key) if "." in key else obj.get(key)
        if key == "order" and isinstance(value, dict):
            value = value.get("id")
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append("" if value is None else str(value))
    return "".join(parts)


def verify_hmac(obj: dict, received_hmac: str, secret: str, field_order: list) -> bool:
    if not received_hmac:
        return False
    message = concatenated_string(obj, field_order)
    computed = hmac_lib.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()
    return hmac_lib.compare_digest(computed, received_hmac)