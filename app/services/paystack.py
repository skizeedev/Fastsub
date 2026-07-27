import requests
from flask import current_app


PAYSTACK_URL = "https://api.paystack.co"


def get_paystack_headers():

    return {
        "Authorization": (
            f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}"
        ),
        "Content-Type": "application/json"
    }


def initialize_payment(
    email,
    amount,
    callback_url
):

    headers = get_paystack_headers()

    data = {
        "email": email,
        "amount": int(amount * 100),
        "callback_url": callback_url
    }

    response = requests.post(
        f"{PAYSTACK_URL}/transaction/initialize",
        json=data,
        headers=headers
    )

    return response.json()


def create_customer(
    email,
    first_name,
    last_name=""
):

    headers = get_paystack_headers()

    data = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name
    }

    response = requests.post(
        f"{PAYSTACK_URL}/customer",
        json=data,
        headers=headers
    )

    return response.json().get("data")


def create_dedicated_account(
    customer_code
):

    headers = get_paystack_headers()

    data = {
        "customer": customer_code
    }

    response = requests.post(
        f"{PAYSTACK_URL}/dedicated_account",
        json=data,
        headers=headers
    )

    return response.json().get("data")
