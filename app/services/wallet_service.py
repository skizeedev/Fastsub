from app import db
from app.models.transaction import Transaction
import uuid


def debit_wallet(user, amount, service_type, recipient=None):

    if user.wallet_balance is None:
        user.wallet_balance = 0

    if user.wallet_balance < amount:
        return {
            "status": "failed",
            "message": "Insufficient balance"
        }

    user.wallet_balance -= amount
    user.total_spent += amount

    transaction = Transaction(
        user_id=user.id,
        service_type=service_type,
        amount=amount,
        recipient=recipient,
        status="success",
        reference=str(uuid.uuid4())
    )

    db.session.add(transaction)
    db.session.commit()

    return {
        "status": "success",
        "reference": transaction.reference
    }


def credit_wallet(user, amount):

    if user.wallet_balance is None:
        user.wallet_balance = 0

    if user.total_funded is None:
        user.total_funded = 0

    user.wallet_balance += amount
    user.total_funded += amount

    db.session.commit()

    return {
        "status": "success"
    }
