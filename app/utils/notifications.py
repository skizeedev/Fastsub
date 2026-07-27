from app import db
from app.models.notification import Notification


def create_notification(
    user_id,
    title,
    message,
    notification_type="general"
):

    notification = Notification(

        user_id=user_id,

        title=title,

        message=message,

        notification_type=notification_type

    )

    db.session.add(notification)
