import requests
from flask import current_app


def get_cable_tv_types():
    """
    Fetch available cable TV providers from Clubkonnect/Nellobytes endpoint.
    """
    url = "https://www.nellobytesystems.com/APICableTVTypeV2.asp"

    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"]
    }

    response = requests.get(url, params=params, timeout=60)
    print("CABLE TYPES STATUS:", response.status_code)
    print("CABLE TYPES BODY:", response.text)

    response.raise_for_status()
    return response.json()


def get_cable_tv_packages():
    """
    Fetch available cable TV packages.
    """
    url = "https://www.nellobytesystems.com/APICableTVPackagesV2.asp"

    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"]
    }

    response = requests.get(url, params=params, timeout=60)
    print("CABLE PACKAGES STATUS:", response.status_code)
    print("CABLE PACKAGES BODY:", response.text)

    response.raise_for_status()
    return response.json()


def verify_cable_tv(cable_tv, smartcard_no):
    """
    Verify cable smartcard / IUC number.
    """
    url = "https://www.nellobytesystems.com/APIVerifyCableTVV1.asp"

    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"],
        "CableTV": cable_tv,
        "SmartCardNo": smartcard_no,
    }

    response = requests.get(url, params=params, timeout=60)
    print("VERIFY CABLE STATUS:", response.status_code)
    print("VERIFY CABLE BODY:", response.text)

    response.raise_for_status()
    return response.json()


def buy_cable_tv(cable_tv, package, smartcard_no, phone, request_id, callback_url=None):
    """
    Purchase cable TV subscription.
    """
    url = "https://www.nellobytesystems.com/APICableTVV1.asp"

    params = {
        "UserID": current_app.config["CLUBKONNECT_USERID"],
        "APIKey": current_app.config["CLUBKONNECT_APIKEY"],
        "CableTV": cable_tv,
        "Package": package,
        "SmartCardNo": smartcard_no,
        "PhoneNo": phone,
        "RequestID": request_id,
    }

    if callback_url:
        params["CallBackURL"] = callback_url

    response = requests.get(url, params=params, timeout=60)
    print("BUY CABLE STATUS:", response.status_code)
    print("BUY CABLE BODY:", response.text)

    response.raise_for_status()
    return response.json()
