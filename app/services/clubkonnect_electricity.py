import requests

from flask import current_app


BASE_URL = "https://www.nellobytesystems.com"


def verify_meter(
    electric_company,
    meter_no,
    meter_type
):
    """
    Verify electricity meter details before payment.
    """

    url = (
        f"{BASE_URL}/APIVerifyElectricityV1.asp"
    )

    params = {
        "UserID": current_app.config[
            "CLUBKONNECT_USERID"
        ],
        "APIKey": current_app.config[
            "CLUBKONNECT_APIKEY"
        ],
        "ElectricCompany": electric_company,
        "MeterNo": meter_no,
        "MeterType": meter_type
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    print("VERIFY ELECTRICITY STATUS:", response.status_code)
    print("VERIFY ELECTRICITY BODY:", response.text)

    return response.json()


def buy_electricity(
    electric_company,
    meter_type,
    meter_no,
    amount,
    phone,
    request_id,
    callback_url=""
):
    """
    Purchase electricity bill / token.
    """

    url = (
        f"{BASE_URL}/APIElectricityV1.asp"
    )

    params = {
        "UserID": current_app.config[
            "CLUBKONNECT_USERID"
        ],
        "APIKey": current_app.config[
            "CLUBKONNECT_APIKEY"
        ],
        "ElectricCompany": electric_company,
        "MeterType": meter_type,
        "MeterNo": meter_no,
        "Amount": amount,
        "PhoneNo": phone,
        "RequestID": request_id,
        "CallBackURL": callback_url
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    print("BUY ELECTRICITY STATUS:", response.status_code)
    print("BUY ELECTRICITY BODY:", response.text)
    print("BUY ELECTRICITY PARAMS:", params)

    return response.json()
