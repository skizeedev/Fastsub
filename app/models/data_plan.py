from app import db

class DataPlan(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    network = db.Column(
        db.String(20),
        nullable=False
    )

    plan_code = db.Column(
        db.String(50),
        nullable=False
    )

    plan_name = db.Column(
        db.String(255),
        nullable=False
    )

    cost_price = db.Column(
        db.Float,
        nullable=False
    )

    selling_price = db.Column(
        db.Float,
        nullable=False
    )

    provider = db.Column(
        db.String(50),
        default="clubkonnect"
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    network_code = db.Column(
        db.String(10),
        nullable=False
    )

    provider_plan_id = db.Column(
        db.String(50)
    )

    description = db.Column(
        db.String(255)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "network_code",
            "plan_code",
            name="uq_network_plan"
        ),
    )

    @property
    def profit(self):
        return (
            self.selling_price -
            self.cost_price
        )
