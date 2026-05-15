"""
Robokassa payment gateway client.

Placeholder until registration is complete.
When ready: fill .env with ROBOKASSA_LOGIN, ROBOKASSA_PASSWORD1, ROBOKASSA_PASSWORD2
"""
import hashlib
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class RobokassaClient:
    def __init__(self, login: str = "", password1: str = "", password2: str = ""):
        self.login = login
        self.password1 = password1
        self.password2 = password2

    def is_configured(self) -> bool:
        return bool(self.login and self.password1)

    def generate_payment_url(self, inv_id: int, amount: float, description: str = "Оплата пакета анализов") -> str:
        signature = hashlib.md5(
            f"{self.login}:{amount:.2f}:{inv_id}:{self.password1}".encode()
        ).hexdigest()

        params = {
            "MerchantLogin": self.login,
            "OutSum": f"{amount:.2f}",
            "InvId": inv_id,
            "Description": description,
            "SignatureValue": signature,
            "IsTest": 0,
        }
        return "https://auth.robokassa.ru/Merchant/Index.aspx?" + urlencode(params)

    async def check_payment_status(self, inv_id: int) -> bool:
        """
        Check if invoice is paid via Invoice API (JWT).
        Returns True if paid.
        """
        import json
        import base64
        import hmac

        if not self.is_configured():
            logger.warning("Robokassa not configured, check_payment_status stub")
            return False

        header = base64url_encode(json.dumps({"typ": "JWT", "alg": "MD5"}).encode())
        payload = base64url_encode(json.dumps({
            "MerchantLogin": self.login,
            "InvoiceStatuses": ["paid"],
            "InvoiceTypes": ["onetime", "reusable"],
            "CurrentPage": 1,
            "PageSize": 10,
            "Keywords": str(inv_id),
        }).encode())

        sign_input = f"{header}.{payload}"
        key = f"{self.login}:{self.password1}"
        signature = base64url_encode(
            hmac.new(key.encode(), sign_input.encode(), hashlib.md5).digest()
        )

        token = f"{header}.{payload}.{signature}"

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://services.robokassa.ru/InvoiceServiceWebApi/api/GetInvoiceInformationList",
                data=json.dumps(token),
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Robokassa API error: {resp.status}")
                    return False
                data = await resp.json()
                return data.get("totalCount", 0) > 0

    def verify_result_url(self, out_sum: str, inv_id: str, signature: str) -> bool:
        expected = hashlib.md5(
            f"{out_sum}:{inv_id}:{self.password2}".encode()
        ).hexdigest().upper()
        return expected == signature.upper()


def base64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


robokassa = RobokassaClient()
