import requests

from flask import current_app


def buy_data(
    network,
    data_plan,
    phone,
    request_id
):

    url = (
        "https://www.nellobytesystems.com/"
        "APIDatabundleV1.asp"
    )

    params = {
        "UserID":
            current_app.config[
                "CLUBKONNECT_USERID"
            ],

        "APIKey":
            current_app.config[
                "CLUBKONNECT_APIKEY"
            ],

        "MobileNetwork":
            network,

        "DataPlan":
            data_plan,

        "MobileNumber":
            phone,

        "RequestID":
            request_id
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    print("STATUS:", response.status_code)
    print("BODY:", response.text)
    print(url)
    print(params)

    return response.json()
