"""
Central config, loaded from environment variables (or a .env file if you have
python-dotenv installed — this will silently no-op otherwise).

Required env vars:
    PAYMOB_API_KEY            -> Dashboard > Settings > API Keys > API Key
    PAYMOB_SECRET_KEY         -> Dashboard > Settings > API Keys > Secret Key
    PAYMOB_PUBLIC_KEY         -> Dashboard > Settings > API Keys > Public Key
    PAYMOB_INTEGRATION_ID     -> Developers > Payment Integrations (the 3DS/online one)
    PAYMOB_MOTO_INTEGRATION_ID-> Developers > Payment Integrations (the MOTO one)
    PAYMOB_IFRAME_ID          -> Developers > iFrames
    PAYMOB_HMAC_SECRET        -> Dashboard > Settings > Account Info > HMAC
    PUBLIC_BASE_URL           -> your current ngrok https URL, e.g. https://xxxx.ngrok-free.app
    PAYMOB_BASE_URL           -> defaults to https://accept.paymob.com (Egypt)
    PAYMOB_CURRENCY           -> defaults to EGP
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    def __init__(self):
        self.base_url = os.environ.get("PAYMOB_BASE_URL", "https://accept.paymob.com")
        self.api_key = os.environ["PAYMOB_API_KEY"]
        self.secret_key = os.environ["PAYMOB_SECRET_KEY"]
        self.public_key = os.environ["PAYMOB_PUBLIC_KEY"]
        self.integration_id = int(os.environ["PAYMOB_INTEGRATION_ID"])    
        self.moto_integration_id = int(os.environ["PAYMOB_MOTO_INTEGRATION_ID"])
        self.iframe_id = os.environ["PAYMOB_IFRAME_ID"]
        self.hmac_secret = os.environ["PAYMOB_HMAC_SECRET"]
        self.public_base_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")
        self.currency = os.environ.get("PAYMOB_CURRENCY", "EGP")


settings = Settings()