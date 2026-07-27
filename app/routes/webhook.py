from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.user import User
from app.models.wallet_transaction import WalletTransaction

import hashlib
import hmac

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():

    # -------------------------------
    # Verify Paystack Signature
    # -------------------------------
    signature = request.headers.get("x-paystack-signature")

    computed_signature = hmac.new(
        current_app.config["PAYSTACK_SECRET_KEY"].encode(),
        request.data,
        hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        return jsonify({"status": "invalid signature"}), 401

    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"status": "invalid payload"}), 400

    event = payload.get("event")

    if event != "charge.success":
        return jsonify({"status": "ignored"}), 200

    data = payload.get("data", {})

    # We only process Dedicated Virtual Account payments here
    if data.get("channel") != "dedicated_nuban":
        return jsonify({"status": "ignored"}), 200

    customer = data.get("customer", {})
    customer_code = customer.get("customer_code")

    if not customer_code:
        return jsonify({"status": "customer missing"}), 400

    user = User.query.filter_by(
        customer_code=customer_code
    ).first()

    if not user:
        return jsonify({"status": "user not found"}), 200

    amount = data.get("amount", 0) / 100
    reference = data.get("reference")

    existing = WalletTransaction.query.filter_by(
        reference=reference
    ).first()

    if existing:
        return jsonify({"status": "duplicate"}), 200

    # Credit wallet
    user.wallet_balance += amount

    wallet = WalletTransaction(
        user_id=user.id,
        amount=amount,
        transaction_type="credit",
        source="paystack",
        reference=reference,
        description="Wallet Funding via Dedicated Virtual Account",
        status="success",
        performed_by="Paystack"
    )

    db.session.add(wallet)
    db.session.commit()

    return jsonify({"status": "success"}), 200
