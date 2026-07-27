from app import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    google_id = db.Column(
        db.String(255),
        unique=True,
        nullable=True
    )

    auth_provider = db.Column(
        db.String(50),
        nullable=False,
        default="local"
    )

    verification_email_sent_at = db.Column(
        db.DateTime,
        nullable=True
    )


    profile_picture = db.Column(
        db.String(255)
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    wallet_balance = db.Column(
        db.Float,
        default=0.0
    )

    total_funded = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    total_spent = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    referral_earnings = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    referral_code = db.Column(
        db.String(20),
        unique=True
    )

    referred_by = db.Column(
        db.String(20)
    )

    phone_number = db.Column(
        db.String(20),
        unique=True
    )

    is_verified = db.Column(
        db.Boolean,
        default=False
    )


    is_admin = db.Column(
        db.Boolean,
        default=False
    )

    is_active_user = db.Column(
        db.Boolean,
        default=True
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    transactions = db.relationship(
        "Transaction",
        backref="user",
        lazy=True
    )

    wallet_transactions = db.relationship(
        "WalletTransaction",
        backref="user",
        lazy=True
    )

    notifications = db.relationship(
        "Notification",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # Paystack Customer
    paystack_customer_code = db.Column(db.String(100), nullable=True)
    paystack_customer_id = db.Column(db.String(100), nullable=True)

    # Dedicated Virtual Account
    virtual_account_number = db.Column(db.String(20), nullable=True)
    virtual_account_name = db.Column(db.String(255), nullable=True)
    virtual_bank_name = db.Column(db.String(100), nullable=True)
    virtual_account_reference = db.Column(db.String(100), nullable=True)

    paystack_dedicated_account_id = db.Column(db.String(100), nullable=True)

    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))

    def __repr__(self):
        return f"<User {self.username}>"
