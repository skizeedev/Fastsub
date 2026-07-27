import requests
from flask import current_app


BASE_URL = "https://api.paystack.co"


def create_virtual_account(user):

    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone
    }

    customer = requests.post(
        f"{BASE_URL}/customer",
        json=payload,
        headers=headers
    ).json()

    customer_code = customer["data"]["customer_code"]

    payload = {
        "customer": customer_code,
        "preferred_bank": "wema-bank"
    }

    account = requests.post(
        f"{BASE_URL}/dedicated_account",
        json=payload,
        headers=headers
    ).json()

    data = account["data"]

    return {
        "customer_code": customer_code,
        "customer_id": data["customer"]["id"],
        "bank_name": data["bank"]["name"],
        "account_name": data["account_name"],
        "account_number": data["account_number"]
    }
