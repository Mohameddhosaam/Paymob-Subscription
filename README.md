# Paymob Subscriptions Demo

A minimal Flask app + client wrapper demonstrating the full Paymob
subscription lifecycle: create a plan, create a subscription, attach a
secondary card, change the primary card, and suspend the subscription.

Built against Paymob's official **"Paymob Subscription Module API"** Postman
collection (`PaymobAccept/API-Postman-Collections`).

## Key thing to understand before you start

A subscription is **not** created by paying with an already-saved card
token. It's created through the **Intentions API** (`POST /v1/intention/`),
which returns a `client_secret`. You (or the customer) must open Paymob's
**Unified Checkout** page with that `client_secret` and enter a **real card**,
completing 3DS. Paymob attaches that card to the subscription automatically.

This means the flow is **not fully headless** — creating a subscription and
adding a secondary card each require one manual browser step. Everything
else (plan creation, changing primary card, suspending) is fully automated.

## Files

| File | Purpose |
| --- | --- |
| `config.py` | Loads settings from environment variables / `.env` |
| `paymob_client.py` | Wrapper around all Paymob HTTP calls used here |
| `hmac_utils.py` | Verifies HMAC signatures on incoming webhooks |
| `app.py` | Flask server: checkout routes + webhook receivers |
| `demo_flow.py` | Scripted walkthrough of the full subscription lifecycle |
| `.env.example` | Template for required environment variables |
| `requirements.txt` | Python dependencies |

## Two different auth schemes (important)

Paymob's subscription APIs mix two auth methods — `paymob_client.py` handles
this correctly, but it's worth knowing when reading the code:

- **`Bearer {auth_token}`** (a short-lived token generated from your API key)
  — used for subscription plans and all subscription *lifecycle* actions:
  list, suspend, resume, cancel, list cards, change primary card, delete card.
- **`Token {secret_key}`** (your Secret Key, used directly) — used **only**
  for the Intentions API (`POST /v1/intention/`), i.e. creating a subscription
  or attaching a new card to one.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in every value:

```bash
cp .env.example .env
```

| Variable | Where to find it |
| --- | --- |
| `PAYMOB_API_KEY` | Dashboard → Settings → API Keys → API Key |
| `PAYMOB_SECRET_KEY` | Dashboard → Settings → API Keys → Secret Key |
| `PAYMOB_PUBLIC_KEY` | Dashboard → Settings → API Keys → Public Key |
| `PAYMOB_INTEGRATION_ID` | Developers → Payment Integrations — your **3DS/online** card integration |
| `PAYMOB_MOTO_INTEGRATION_ID` | Developers → Payment Integrations — your **MOTO** integration |
| `PAYMOB_IFRAME_ID` | Developers → iFrames |
| `PAYMOB_HMAC_SECRET` | Settings → Account Info → HMAC |
| `PUBLIC_BASE_URL` | Your current ngrok `https://...` URL (see step 3) |
| `PAYMOB_CURRENCY` | Defaults to `EGP` |

### 3. Start ngrok

```bash
ngrok http 5000
```

Copy the `https://xxxx.ngrok-free.app` URL into `.env` as
`PUBLIC_BASE_URL`.

**Note:** every time you restart ngrok you get a new subdomain — you'll need
to repeat this step and step 4 below, or webhooks/redirects will silently go
to a dead tunnel.

### 4. Register the ngrok URL in the Paymob dashboard

On **both** your 3DS integration and your MOTO integration, set:

- **Transaction Processed Callback** → `https://xxxx.ngrok-free.app/webhook/transaction`
- **Transaction Response Callback** → `https://xxxx.ngrok-free.app/webhook/transaction`

(The subscription plan's `webhook_url` is set automatically by the code from
`PUBLIC_BASE_URL` — no manual dashboard step needed for that one.)

### 5. Start the Flask app

Leave this running in its own terminal — you'll want to watch its logs live.

```bash
python app.py
```

## Running the demo

In a second terminal:

```bash
python demo_flow.py
```

The script will:

1. **Create a subscription plan.**
2. **Print a URL and pause.** Open it in an actual browser — you'll land on
   Paymob's Unified Checkout page. Enter a Paymob test card, complete 3DS,
   then return to the terminal and press Enter.
3. **Look up the resulting subscription** via `plan_id`.
4. **Print a second URL and pause**, for attaching a secondary card. Open it,
   use a **different** test card, complete 3DS, press Enter again.
5. **Automatically:** list the subscription's cards, promote the secondary
   card to primary, suspend the subscription, and print the final state.

While it runs, keep an eye on the `app.py` terminal — you should see
`Verified TRANSACTION webhook` log lines after each checkout, confirming
Paymob successfully reached your server.

## Routes reference (`app.py`)

| Route | Purpose |
| --- | --- |
| `GET /checkout/<amount_cents>` | Standalone card tokenization demo (unrelated to subscriptions) |
| `GET /subscribe/<plan_id>/<amount_cents>` | Creates a subscription — visit in a browser |
| `GET /subscribe/add-card/<subscription_id>/<amount_cents>` | Attaches a secondary card — visit in a browser |
| `POST /webhook/transaction` | Server-to-server transaction callback (HMAC verified) |
| `GET /webhook/transaction` | Browser redirect target after checkout |
| `POST /webhook/subscription` | Subscription lifecycle webhook |
| `GET /tokens` | Debug: list captured standalone card tokens |
