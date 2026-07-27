from datetime import datetime
from app import db


class Announcement(db.Model):
    __tablename__ = "announcement"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    announcement_type = db.Column(
        db.String(30),
        default="info"
    )
    # info
    # success
    # warning
    # danger
    # promotion

    priority = db.Column(
        db.String(20),
        default="normal"
    )
    # low
    # normal
    # important
    # critical

    active = db.Column(
        db.Boolean,
        default=True
    )

    pinned = db.Column(
        db.Boolean,
        default=False
    )

    popup = db.Column(
        db.Boolean,
        default=False
    )

    start_date = db.Column(
        db.DateTime,
        nullable=True
    )

    expiry_date = db.Column(
        db.DateTime,
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def __repr__(self):
        return f"<Announcement {self.title}>"
