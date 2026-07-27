import requests
from flask import current_app

BASE_URL = "https://api.paystack.co"


def create_customer(user):
    url = f"{BASE_URL}/customer"

    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": user.email,
        "first_name": user.username,
        "last_name": ""
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30
    )

    return response.json()


def create_dedicated_account(customer_code):
    url = f"{BASE_URL}/dedicated_account"

    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "customer": customer_code,
        "preferred_bank": "wema-bank"
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30
    )

    return response.json()
