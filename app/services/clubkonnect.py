import requests
from flask import current_app


def buy_airtime(network, amount, phone, request_id):

    url = (
        "https://www.nellobytesystems.com/APIAirtimeV1.asp"
        f"?UserID={current_app.config['CLUBKONNECT_USERID']}"
        f"&APIKey={current_app.config['CLUBKONNECT_APIKEY']}"
        f"&MobileNetwork={network}"
        f"&Amount={amount}"
        f"&MobileNumber={phone}"
        f"&RequestID={request_id}"
    )

    response = requests.get(url)

    return response.json()
