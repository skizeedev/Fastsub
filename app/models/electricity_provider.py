from app import db


class ElectricityProvider(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        unique=True
    )

    provider_code = db.Column(
        db.String(20)
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    provider_plan_id = db.Column(
        db.String(50),
        nullable=True
    )
