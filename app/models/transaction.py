from datetime import datetime
from app import db


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # general
    service_type = db.Column(db.String(50), nullable=False)   # airtime, data, electricity, cable_tv
    amount = db.Column(db.Float, nullable=False)
    recipient = db.Column(db.String(150), nullable=True)      # phone / meter no / smartcard no
    status = db.Column(db.String(20), default="pending")      # pending, success, failed
    reference = db.Column(db.String(100), unique=True, nullable=False)

    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # provider / reconciliation
    provider_reference = db.Column(db.String(100), nullable=True)
    provider_status = db.Column(db.String(100), nullable=True)
    provider_response = db.Column(db.Text, nullable=True)

    # ---------- AIRTIME / DATA ----------
    network = db.Column(db.String(50), nullable=True)
    plan_name = db.Column(db.String(255), nullable=True)
    product_name = db.Column(db.String(255), nullable=True)

    # ---------- ELECTRICITY ----------
    customer_name = db.Column(db.String(255), nullable=True)

    electric_company_code = db.Column(db.String(20), nullable=True)
    electric_company_name = db.Column(db.String(150), nullable=True)

    meter_number = db.Column(db.String(100), nullable=True)
    meter_type = db.Column(db.String(50), nullable=True)

    token = db.Column(db.String(255), nullable=True)
    units = db.Column(db.String(100), nullable=True)

    # ---------- CABLE TV ----------
    cable_tv_code = db.Column(db.String(20), nullable=True)
    cable_tv_name = db.Column(db.String(150), nullable=True)

    package_code = db.Column(db.String(50), nullable=True)
    package_name = db.Column(db.String(255), nullable=True)

    smartcard_number = db.Column(db.String(100), nullable=True)

    # ---------- BETTING ----------
    betting_company_code = db.Column(db.String(50), nullable=True)
    betting_company_name = db.Column(db.String(150), nullable=True)

    betting_customer_id = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<Transaction {self.reference}>"
