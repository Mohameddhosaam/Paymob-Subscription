"""
Thin wrapper around the Paymob HTTP APIs, corrected against Paymob's official
"Paymob Subscription Module API" Postman collection (PaymobAccept/API-Postman-Collections).

Two different auth schemes are used:
  - Bearer {auth_token}  -> generated from the API key, used for:
        order/payment_key/classic pay, subscription-plans, and all
        subscription LIFECYCLE actions (list/suspend/resume/cancel/cards/
        change-primary-card/delete-card).
  - Token {secret_key}   -> your Secret Key directly, used ONLY for the
        Intentions API (POST /v1/intention/), which is what actually CREATES
        a subscription or attaches a new card to one.

Key fact this file encodes: a subscription is never
created by paying with an existing saved card token. It requires the
Intentions API, which returns a client_secret. The customer (or you, in test
mode) must complete a real checkout with a NEW card via Paymob's Unified
Checkout page. Paymob then attaches that card to the subscription itself.
"""


import requests
from config import settings

TIMEOUT = 30


class PaymobError(RuntimeError):
    def __init__(self, response: requests.Response):
        self.status_code = response.status_code
        self.body = response.text
        super().__init__(f"Paymob API error {response.status_code}: {response.text}")


def _check(response: requests.Response) -> dict:
    if not response.ok:
        raise PaymobError(response)
    return response.json() if response.content else {}


class PaymobClient:
    def __init__(self):
        self.base_url = settings.base_url
        self._auth_token = None  # classic Accept token (~1hr lifetime)

    # ---------------------------------------------------------------- #
    # Authentication
    # ---------------------------------------------------------------- #
    def authenticate(self) -> str:
        url = f"{self.base_url}/api/auth/tokens"
        resp = requests.post(url, json={"api_key": settings.api_key}, timeout=TIMEOUT)
        data = _check(resp)
        self._auth_token = data["token"]
        return self._auth_token

    def _auth(self) -> str:
        return self._auth_token or self.authenticate()

    def _bearer_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._auth()}", "Content-Type": "application/json"}

    def _secret_key_headers(self) -> dict:
        return {"Authorization": f"Token {settings.secret_key}", "Content-Type": "application/json"}

    # ---------------------------------------------------------------- #
    # Classic Accept flow (order -> payment key -> iframe): used only for
    # the standalone card-tokenization demo route, unrelated to subscriptions.
    # ---------------------------------------------------------------- #
    def create_order(self, amount_cents: int, merchant_order_id: str) -> dict:
        url = f"{self.base_url}/api/ecommerce/orders"
        payload = {
            "auth_token": self._auth(),
            "delivery_needed": False,
            "amount_cents": amount_cents,
            "currency": settings.currency,
            "merchant_order_id": merchant_order_id,
            "items": [],
        }
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        return _check(resp)

    def get_payment_key(self, order_id: int, amount_cents: int, billing_data: dict,
                         integration_id: int | None = None) -> str:
        url = f"{self.base_url}/api/acceptance/payment_keys"
        payload = {
            "auth_token": self._auth(),
            "amount_cents": amount_cents,
            "expiration": 3600,
            "order_id": order_id,
            "billing_data": billing_data,
            "currency": settings.currency,
            "integration_id": integration_id or settings.integration_id,
            "lock_order_when_paid": True,
        }
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        return _check(resp)["token"]

    def iframe_url(self, payment_key_token: str) -> str:
        return (
            f"{self.base_url}/api/acceptance/iframes/{settings.iframe_id}"
            f"?payment_token={payment_key_token}"
        )

    # ---------------------------------------------------------------- #
    # Subscription Plans
    # ---------------------------------------------------------------- #
    def create_subscription_plan(
        self,
        name: str,
        amount_cents: int,
        frequency_days: int,
        reminder_days: int = 3,
        retrial_days: int = 3,
        webhook_url: str | None = None,
    ) -> dict:
        url = f"{self.base_url}/api/acceptance/subscription-plans"
        payload = {
            "name": name,
            "is_active": True,
            "amount_cents": amount_cents,
            "currency": settings.currency,
            "frequency": frequency_days,
            "reminder_days": reminder_days,
            "retrial_days": retrial_days,
            "plan_type": "rent",
            "number_of_deductions": None,
            "use_transaction_amount": False,
            "integration": settings.moto_integration_id,  # MOTO ID, for renewals
            "webhook_url": webhook_url or f"{settings.public_base_url}/webhook/subscription",
        }
        resp = requests.post(url, json=payload, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def list_subscription_plans(self) -> dict:
        url = f"{self.base_url}/api/acceptance/subscription-plans"
        resp = requests.get(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def suspend_subscription_plan(self, plan_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscription-plans/{plan_id}/suspend"
        resp = requests.post(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def resume_subscription_plan(self, plan_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscription-plans/{plan_id}/resume"
        resp = requests.post(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    # ---------------------------------------------------------------- #
    # Subscription creation / card attachment — Intentions API.
    # These are the calls that actually create/modify a subscription.
    # Auth here is "Token {secret_key}", NOT Bearer.
    # ---------------------------------------------------------------- #
    def create_subscription_intention(
        self,
        subscription_plan_id: int,
        amount_cents: int,
        billing_data: dict,
        notification_url: str | None = None,
        redirection_url: str | None = None,
    ) -> dict:
        """POST /v1/intention/ with subscription_plan_id.
        Returns a dict containing 'client_secret' — open the Unified Checkout
        with it and complete a real card + 3DS entry to finish creating the
        subscription."""
        url = f"{self.base_url}/v1/intention/"
        payload = {
            "amount": amount_cents,
            "currency": settings.currency,
            "payment_methods": [settings.integration_id],  # 3DS integration, NOT moto
            "subscription_plan_id": subscription_plan_id,
            "items": [{
                "name": "Subscription",
                "amount": amount_cents,
                "description": "Subscription payment",
                "quantity": 1,
            }],
            "billing_data": billing_data,
        }
        if notification_url:
            payload["notification_url"] = notification_url
        if redirection_url:
            payload["redirection_url"] = redirection_url
        resp = requests.post(url, json=payload, headers=self._secret_key_headers(), timeout=TIMEOUT)
        return _check(resp)

    def add_secondary_card_intention(
        self,
        subscription_id: int,
        amount_cents: int,
        billing_data: dict,
    ) -> dict:
        """Same as above but uses subscriptionv2_id to attach a new card to an
        EXISTING subscription instead of creating one."""
        url = f"{self.base_url}/v1/intention/"
        payload = {
            "amount": amount_cents,
            "currency": settings.currency,
            "payment_methods": [settings.integration_id],
            "subscriptionv2_id": subscription_id,
            "items": [{
                "name": "Secondary card",
                "amount": amount_cents,
                "description": "Add secondary card",
                "quantity": 1,
            }],
            "billing_data": billing_data,
        }
        resp = requests.post(url, json=payload, headers=self._secret_key_headers(), timeout=TIMEOUT)
        return _check(resp)

    def checkout_url(self, client_secret: str) -> str:
        return f"{self.base_url}/unifiedcheckout/?publicKey={settings.public_key}&clientSecret={client_secret}"

    # ---------------------------------------------------------------- #
    # Subscriptions — lifecycle & inspection (Bearer auth)
    # ---------------------------------------------------------------- #
    def get_subscription(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}"
        resp = requests.get(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def find_subscriptions_by_plan(self, plan_id: int) -> dict:
        """GET /api/acceptance/subscriptions?plan_id=... — how you locate the
        subscription_id after a checkout completes. Other supported filters:
        transaction, state, starts_at, next_billing, reminder_date, ends_at."""
        url = f"{self.base_url}/api/acceptance/subscriptions"
        resp = requests.get(url, headers=self._bearer_headers(),
                             params={"plan_id": plan_id}, timeout=TIMEOUT)
        return _check(resp)

    def list_subscription_cards(self, subscription_id: str) -> list:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/card-tokens"
        resp = requests.get(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def change_primary_card(self, subscription_id: str, card_id: int) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/change-primary-card"
        resp = requests.post(url, json={"card": card_id}, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def delete_secondary_card(self, subscription_id: str, card_id: int) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/delete-card"
        resp = requests.post(url, json={"card": card_id}, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def suspend_subscription(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/suspend"
        resp = requests.post(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def resume_subscription(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/resume"
        resp = requests.post(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def cancel_subscription(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/cancel"
        resp = requests.post(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def last_transaction(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/last-transaction"
        resp = requests.get(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)

    def list_subscription_transactions(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/api/acceptance/subscriptions/{subscription_id}/transactions"
        resp = requests.get(url, headers=self._bearer_headers(), timeout=TIMEOUT)
        return _check(resp)