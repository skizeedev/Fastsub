from datetime import datetime
from app import db


class WalletTransaction(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    reference = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    transaction_type = db.Column(
        db.String(20),
        nullable=False
    )
    # credit / debit

    source = db.Column(
        db.String(50),
        nullable=True
    )
    # paystack, admin, referral, refund, bonus, commission

    description = db.Column(
        db.String(255),
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="success"
    )

    performed_by = db.Column(
        db.String(100),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def __repr__(self):
        return f"<WalletTransaction {self.reference}>"
