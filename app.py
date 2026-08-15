"""
Run this, tunnel it with ngrok, register the ngrok https URL in the Paymob
dashboard (Integration > Transaction Processed Callback, and the Subscription
Plan's webhook_url), then use demo_flow.py to drive the plan/subscription
flow. Two routes below require you to visit them in an actual browser and
complete a real test-card + 3DS entry — that's how Paymob subscriptions work,
they cannot be created purely headlessly.

"""
import logging
from flask import Flask, request, redirect, jsonify

from config import settings
from paymob_client import PaymobClient
from hmac_utils import verify_hmac, TRANSACTION_FIELD_ORDER, TOKEN_FIELD_ORDER

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("paymob-app")

app = Flask(__name__)
client = PaymobClient()

CAPTURED_CARD_TOKENS = []

BILLING_DATA = {
    "first_name": "Test", "last_name": "Customer",
    "email": "test.customer@example.com", "phone_number": "+201000000000",
    "apartment": "NA", "floor": "NA", "street": "NA", "building": "NA",
    "city": "Cairo", "state": "Cairo", "country": "EG",
}


@app.route("/checkout/<int:amount_cents>")
def checkout(amount_cents: int):
    """Standalone card tokenization demo — unrelated to subscriptions."""
    order = client.create_order(amount_cents, merchant_order_id=f"order-{amount_cents}-demo")
    payment_key = client.get_payment_key(order["id"], amount_cents, BILLING_DATA)
    return redirect(client.iframe_url(payment_key))


@app.route("/subscribe/<int:plan_id>/<int:amount_cents>")
def subscribe(plan_id: int, amount_cents: int):
    """Creates a subscription intention and sends you to Paymob's Unified
    Checkout to enter a card. Completing checkout finishes subscription creation."""
    intention = client.create_subscription_intention(plan_id, amount_cents, BILLING_DATA)
    log.info("Created subscription intention: %s", intention.get("id"))
    return redirect(client.checkout_url(intention["client_secret"]))


@app.route("/subscribe/add-card/<int:subscription_id>/<int:amount_cents>")
def add_secondary_card(subscription_id: int, amount_cents: int):
    """Attaches a new (secondary) card to an existing subscription."""
    intention = client.add_secondary_card_intention(subscription_id, amount_cents, BILLING_DATA)
    log.info("Created add-card intention: %s", intention.get("id"))
    return redirect(client.checkout_url(intention["client_secret"]))


@app.route("/webhook/transaction", methods=["POST"])
def transaction_webhook():
    payload = request.get_json(force=True, silent=True) or {}
    callback_type = payload.get("type", "TRANSACTION")
    obj = payload.get("obj", payload)
    received_hmac = request.args.get("hmac", "")

    if callback_type == "TOKEN":
        if not verify_hmac(obj, received_hmac, settings.hmac_secret, TOKEN_FIELD_ORDER):
            log.warning("Rejected TOKEN webhook with invalid HMAC")
            return jsonify({"error": "invalid hmac"}), 401
        card_token = obj.get("token")
        log.info("Verified TOKEN webhook: card_token=%s masked_pan=%s", card_token, obj.get("masked_pan"))
        if card_token:
            CAPTURED_CARD_TOKENS.append(card_token)
        return jsonify({"received": True}), 200

    if not verify_hmac(obj, received_hmac, settings.hmac_secret, TRANSACTION_FIELD_ORDER):
        log.warning("Rejected TRANSACTION webhook with invalid HMAC")
        return jsonify({"error": "invalid hmac"}), 401

    success = obj.get("success")
    log.info("Verified TRANSACTION webhook: success=%s order_id=%s",
              success, (obj.get("order") or {}).get("id"))
    return jsonify({"received": True}), 200


@app.route("/webhook/transaction", methods=["GET"])
def transaction_response_callback():
    success = request.args.get("success")
    return f"Payment {'succeeded' if success == 'true' else 'failed/pending'}. You can close this tab."


@app.route("/webhook/subscription", methods=["POST"])
def subscription_webhook():
    payload = request.get_json(force=True, silent=True) or {}
    log.info("Subscription webhook event: %s", payload)
    return jsonify({"received": True}), 200


@app.route("/tokens", methods=["GET"])
def tokens():
    return jsonify({"card_tokens": CAPTURED_CARD_TOKENS})


if __name__ == "__main__":
    app.run(port=5000, debug=True)