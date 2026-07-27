import requests

from app import db
from app.models.data_plan import DataPlan


def sync_data_plans():

    url = (
        "https://www.nellobytesystems.com/"
        "APIDatabundlePlansV2.asp"
    )

    params = {
        "UserID": "CK101281055"
    }

    response = requests.get(
        url,
        params=params
    )

    data = response.json()

    networks = data["MOBILE_NETWORK"]

    for network_name, network_data in networks.items():

        network_code = network_data[0]["ID"]

        products = network_data[0]["PRODUCT"]

        for product in products:

            plan_code = str(
                product["PRODUCT_CODE"]
            )

            provider_plan_id = str(
                product["PRODUCT_ID"]
            )

            amount = float(
                str(
                    product["PRODUCT_AMOUNT"]
                ).replace(",", "")
            )

            if amount < 500:
                selling_price = amount + 20

            elif amount < 2000:
                selling_price = amount + 30

            elif amount < 5000:
                selling_price = amount + 50

            else:
                selling_price = amount + 100



            existing = DataPlan.query.filter_by(
                network_code=network_code,
                plan_code=plan_code
            ).first()

            if existing:

                existing.provider_plan_id = str(
                    product["PRODUCT_ID"]
                )

                existing.cost_price = amount

                if amount < 500:
                    existing.selling_price = amount + 20

                elif amount < 2000:
                    existing.selling_price = amount + 30

                elif amount < 5000:
                    existing.selling_price = amount + 50

                else:
                    existing.selling_price = amount + 100

                continue


            plan = DataPlan(
                network=network_name.replace(
                    "m_",
                    ""
                ),
                network_code=network_code,
                plan_code=plan_code,
                provider_plan_id=provider_plan_id,
                plan_name=product["PRODUCT_NAME"],
                cost_price=amount,
                selling_price=selling_price,
                active=True,
                provider="clubkonnect"
            )

            db.session.add(plan)

    db.session.commit()

    return True
