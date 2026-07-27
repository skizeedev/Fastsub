import requests
from flask import current_app

BASE_URL = "https://www.nellobytesystems.com"


def get_betting_companies():
    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"]
    }

    url = f"{BASE_URL}/APIBettingTypeV2.asp"

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    print("BETTING URL:", response.url)
    print("STATUS:", response.status_code)
    print(response.text)

    return response.json()


def verify_betting_customer(
    betting_company,
    customer_id
):
    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"],
        "BettingCompany": betting_company,
        "CustomerID": customer_id
    }

    response = requests.get(
        f"{BASE_URL}/APIVerifyBettingV1.asp",
        params=params,
        timeout=30
    )

    return response.json()


def fund_betting_wallet(
    betting_company,
    customer_id,
    amount,
    request_id,
    phone,
    callback_url=""
):
    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"],
        "BettingCompany": betting_company,
        "CustomerID": customer_id,
        "Amount": amount,
        "PhoneNo": phone,
        "RequestID": request_id,
        "CallBackURL": callback_url
    }

    response = requests.get(
        f"{BASE_URL}/APIBettingV1.asp",
        params=params,
        timeout=30
    )

    return response.json()


def query_betting_transaction(request_id):
    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"],
        "RequestID": request_id
    }

    response = requests.get(
        f"{BASE_URL}/APIQueryV1.asp",
        params=params,
        timeout=30
    )

    return response.json()
