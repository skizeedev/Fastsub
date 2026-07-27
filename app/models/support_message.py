from app import db
from datetime import datetime


class SupportMessage(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "support_ticket.id"
        ),
        nullable=False
    )

    sender_type = db.Column(
        db.String(20),
        nullable=False
    )
    # user/admin

    message = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
