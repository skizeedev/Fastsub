from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    jsonify
)
from sqlalchemy import func
from app import db
from flask_login import login_required, current_user
from app.models.user import User
from app.models.transaction import Transaction
from app.models.wallet_transaction import WalletTransaction
import uuid
from app.models.data_plan import DataPlan
from app.services.clubkonnect_sync import (
    sync_data_plans
)
from app.models.support_ticket import SupportTicket
from app.models.support_message import SupportMessage
from flask import abort
from functools import wraps
import json
import requests
from app.services.wallet_service import credit_wallet
from app.services.clubkonnect_data import buy_data as purchase_data
from datetime import datetime, timedelta
from app.models.announcement import Announcement
from app.models.notification import Notification


DATA_NETWORK_CODES = {
    "mtn": "01",
    "glo": "02",
    "9mobile": "03",
    "airtel": "04"
}

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        if not getattr(current_user, "is_admin", False):
            abort(403)

        return func(*args, **kwargs)
    return wrapper


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def home():
    return redirect(url_for("auth.login"))



admin_bp = Blueprint(
    "admin",
    __name__
)

@admin_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():

    today = datetime.utcnow().date()

    # ==============================
    # BASIC STATISTICS
    # ==============================

    total_users = User.query.count()

    verified_users = User.query.filter_by(
        is_verified=True
    ).count()

    successful_transactions = Transaction.query.filter_by(
        status="success"
    ).count()

    pending_transactions = Transaction.query.filter_by(
        status="pending"
    ).count()

    failed_transactions = Transaction.query.filter_by(
        status="failed"
    ).count()

    total_wallet_balance = db.session.query(
        func.sum(User.wallet_balance)
    ).scalar() or 0

    today_transactions = Transaction.query.filter(
        func.date(Transaction.created_at) == today
    ).count()

    today_revenue = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.status == "success",
        func.date(Transaction.created_at) == today
    ).scalar() or 0

    # ==============================
    # RECENT TRANSACTIONS
    # ==============================

    recent_transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(10).all()

    # ==============================
    # RECENT USERS
    # ==============================

    recent_users = User.query.order_by(
        User.id.desc()
    ).limit(10).all()

    # ==============================
    # REVENUE - LAST 7 DAYS
    # ==============================

    days = []
    daily_sales = []

    for i in range(6, -1, -1):

        day = today - timedelta(days=i)

        total = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.status == "success",
            func.date(Transaction.created_at) == day
        ).scalar() or 0

        days.append(day.strftime("%a"))
        daily_sales.append(float(total))

    # ==============================
    # SALES BY SERVICE
    # ==============================

    airtime_sales = Transaction.query.filter(
        Transaction.status == "success",
        Transaction.service_type.ilike("%airtime%")
    ).count()

    data_sales = Transaction.query.filter(
        Transaction.status == "success",
        Transaction.service_type.ilike("%data%")
    ).count()

    electricity_sales = Transaction.query.filter(
        Transaction.status == "success",
        Transaction.service_type.ilike("%electricity%")
    ).count()

    cable_sales = Transaction.query.filter(
        Transaction.status == "success",
        Transaction.service_type.ilike("%cable%")
    ).count()

    betting_sales = Transaction.query.filter(
        Transaction.status == "success",
        Transaction.service_type.ilike("%betting%")
    ).count()

    # ==============================
    # TRANSACTION STATUS
    # ==============================

    success_count = successful_transactions
    pending_count = pending_transactions
    failed_count = failed_transactions

    # ==============================
    # RECENT NOTIFICATIONS
    # ==============================

    recent_notifications = Notification.query.order_by(
        Notification.created_at.desc()
    ).limit(5).all()

    # ==============================
    # RENDER DASHBOARD
    # ==============================

    return render_template(
        "admin/dashboard.html",

        total_users=total_users,
        verified_users=verified_users,

        successful_transactions=successful_transactions,
        pending_transactions=pending_transactions,
        failed_transactions=failed_transactions,

        total_wallet_balance=float(total_wallet_balance),
        today_transactions=today_transactions,
        today_revenue=float(today_revenue),

        recent_transactions=recent_transactions,
        recent_users=recent_users,

        days=days,
        daily_sales=daily_sales,

        airtime_sales=airtime_sales,
        data_sales=data_sales,
        electricity_sales=electricity_sales,
        cable_sales=cable_sales,
        betting_sales=betting_sales,

        success_count=success_count,
        pending_count=pending_count,
        failed_count=failed_count,

        recent_notifications=recent_notifications
    )

@admin_bp.route("/dashboard/stats")
@login_required
@admin_required
def dashboard_stats():

    from sqlalchemy import func
    from datetime import datetime

    today = datetime.utcnow().date()

    total_users = User.query.count()

    total_wallet = db.session.query(
        func.sum(User.wallet_balance)
    ).scalar() or 0

    total_transactions = Transaction.query.count()

    success = Transaction.query.filter_by(
        status="success"
    ).count()

    pending = Transaction.query.filter_by(
        status="pending"
    ).count()

    failed = Transaction.query.filter_by(
        status="failed"
    ).count()

    today_revenue = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.status == "success",
        func.date(Transaction.created_at) == today
    ).scalar() or 0

    return jsonify({

        "users": total_users,

        "wallet": total_wallet,

        "transactions": total_transactions,

        "success": success,

        "pending": pending,

        "failed": failed,

        "today_revenue": today_revenue

    })

@admin_bp.route("/users")
@login_required
def admin_users():

    if not current_user.is_admin:
        abort(403)

    search = request.args.get("search", "").strip()

    query = User.query

    if search:

        query = query.filter(
            db.or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.referral_code.ilike(f"%{search}%")
            )
        )

    users = query.order_by(
        User.id.desc()
    ).all()

    return render_template(
        "admin/users.html",
        users=users,
        search=search
    )

@admin_bp.route("/user/<int:user_id>")
@login_required
def admin_view_user(user_id):

    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)

    transactions = Transaction.query.filter_by(
        user_id=user.id
    ).order_by(
        Transaction.created_at.desc()
    ).all()

    wallet_history = WalletTransaction.query.filter_by(
        user_id=user.id
    ).order_by(
        WalletTransaction.created_at.desc()
    ).all()

    total_spent = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == user.id,
        Transaction.status == "success"
    ).scalar() or 0

    total_wallet_credit = db.session.query(
        func.sum(WalletTransaction.amount)
    ).filter(
        WalletTransaction.user_id == user.id,
        WalletTransaction.transaction_type == "credit"
    ).scalar() or 0

    return render_template(
        "admin/user_details.html",
        user=user,
        transactions=transactions,
        wallet_history=wallet_history,
        total_spent=total_spent,
        total_wallet_credit=total_wallet_credit
    )


@admin_bp.route("/user/<int:user_id>/credit", methods=["GET", "POST"])
@login_required
def credit_wallet(user_id):

    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)

    if request.method == "POST":

        amount = float(request.form["amount"])
        reason = request.form["reason"]

        user.wallet_balance += amount

        wallet = WalletTransaction(
            user_id=user.id,
            amount=amount,
            reference=str(uuid.uuid4())[:12],
            transaction_type="credit",
            source="admin",
            description=reason,
            status="success",
            performed_by=current_user.username
        )

        notification = Notification(
            user_id=current_user.id,
            title="Wallet Credited",
            message=f"Admin credited your wallet with ₦{amount:,.2f}",
            notification_type="admin"
        )

        db.session.add(notification)
        db.session.add(wallet)
        db.session.commit()

        flash("Wallet credited successfully.")

        return redirect(
            url_for("admin.admin_view_user", user_id=user.id)
        )

    return render_template(
        "admin/credit_wallet.html",
        user=user
    )


@admin_bp.route("/user/<int:user_id>/debit", methods=["GET", "POST"])
@login_required
def debit_wallet(user_id):

    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)

    if request.method == "POST":

        amount = float(request.form["amount"])
        reason = request.form["reason"]

        if user.wallet_balance < amount:

            flash("User has insufficient balance.")

            return redirect(
                url_for("admin.debit_wallet", user_id=user.id)
            )

        user.wallet_balance -= amount

        wallet = WalletTransaction(
            user_id=user.id,
            amount=amount,
            reference=str(uuid.uuid4())[:12],
            transaction_type="debit",
            source="admin",
            description=reason,
            status="success",
            performed_by=current_user.username
        )

        db.session.add(wallet)
        db.session.commit()

        flash("Wallet debited successfully.")

        return redirect(
            url_for("admin.admin_view_user", user_id=user.id)
        )

    return render_template(
        "admin/debit_wallet.html",
        user=user
    )

@admin_bp.route("/admin/transactions")
@login_required
def admin_transactions():

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    search = request.args.get(
        "search",
        ""
    )

    query = Transaction.query

    if search:

        query = query.filter(
            Transaction.recipient.contains(search)
        )

    transactions = query.order_by(
        Transaction.id.desc()
    ).all()

    return render_template(
        "admin/transactions.html",
        transactions=transactions
    )

@admin_bp.route(
    "/admin/suspend/<int:user_id>"
)
@login_required
def suspend_user(user_id):

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    user = User.query.get_or_404(
        user_id
    )

    user.is_active_user = False

    db.session.commit()

    flash(
        "User suspended"
    )

    return redirect(
        url_for("admin.admin_users")
    )

@admin_bp.route(
    "/admin/activate/<int:user_id>"
)
@login_required
def activate_user(user_id):

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    user = User.query.get_or_404(
        user_id
    )

    user.is_active_user = True

    db.session.commit()

    flash(
        "User activated"
    )

    return redirect(
        url_for("admin.admin_users")
    )

@admin_bp.route(
    "/admin/make-admin/<int:user_id>"
)
@login_required
def make_admin(user_id):

    if not current_user.is_admin:

        return redirect(
            url_for("auth.dashboard")
        )

    user = User.query.get_or_404(
        user_id
    )

    user.is_admin = True

    db.session.commit()

    flash(
        "User promoted"
    )

    return redirect(
        url_for("admin.admin_users")
    )

@admin_bp.route(
    "/admin/remove-admin/<int:user_id>"
)
@login_required
def remove_admin(user_id):

    if not current_user.is_admin:

        return redirect(
            url_for("auth.dashboard")
        )

    user = User.query.get_or_404(
        user_id
    )

    user.is_admin = False

    db.session.commit()

    flash(
        "Admin removed"
    )

    return redirect(
        url_for("auth.admin_users")
    )

@admin_bp.route("/admin/data-plans")
@login_required
def admin_data_plans():

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    search = request.args.get(
        "search",
        ""
    )

    query = DataPlan.query

    if search:

        query = query.filter(
            DataPlan.plan_name.contains(search)
        )

    plans = query.order_by(
        DataPlan.network
    ).all()

    return render_template(
        "admin/data_plan.html",
        plans=plans,
        search=search
    )

@admin_bp.route(
    "/admin/data-plans/add",
    methods=["GET", "POST"]
)
@login_required
def add_data_plan():

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    if request.method == "POST":

        plan = DataPlan(

            network=request.form.get(
                "network"
            ),

            network_code=request.form.get(
                "network_code"
            ),

            plan_code=request.form.get(
                "plan_code"
            ),

            plan_name=request.form.get(
                "plan_name"
            ),

            cost_price=float(
                request.form.get(
                    "cost_price"
                )
            ),

            selling_price=float(
                request.form.get(
                    "selling_price"
                )
            )

        )

        db.session.add(plan)

        db.session.commit()

        flash("Plan added")

        return redirect(
            url_for(
                "admin.admin_data_plans"
            )
        )

    return render_template(
        "admin/add_data_plan.html"
    )

@admin_bp.route(
    "/admin/data-plans/edit/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def edit_data_plan(id):

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    plan = DataPlan.query.get_or_404(id)

    if request.method == "POST":

        plan.cost_price = float(
            request.form.get(
                "cost_price"
            )
        )

        plan.selling_price = float(
            request.form.get(
                "selling_price"
            )
        )

        plan.active = (
            request.form.get(
                "active"
            ) == "on"
        )

        db.session.commit()

        flash("Plan updated")

        return redirect(
            url_for(
                "admin.admin_data_plans"
            )
        )

    return render_template(
        "admin/edit_data_plan.html",
        plan=plan
    )

@admin_bp.route(
    "/admin/data-plans/delete/<int:id>"
)
@login_required
def delete_data_plan(id):

    if not current_user.is_admin:

        flash("Access denied")

        return redirect(
            url_for("auth.dashboard")
        )

    plan = DataPlan.query.get_or_404(id)

    db.session.delete(plan)

    db.session.commit()

    flash("Plan deleted")

    return redirect(
        url_for(
            "admin.admin_data_plans"
        )
    )

@admin_bp.route(
    "/admin/data-plans/toggle/<int:id>"
)
@login_required
def toggle_data_plan(id):

    if not current_user.is_admin:

        return redirect(
            url_for("auth.dashboard")
        )

    plan = DataPlan.query.get_or_404(id)

    plan.active = not plan.active

    db.session.commit()

    flash("Plan updated")

    return redirect(
        url_for(
            "admin.admin_data_plans"
        )
    )

@admin_bp.route("/admin/sync-data")
@login_required
def sync_data():

    if not current_user.is_admin:
        flash("Access denied")
        return redirect(
            url_for("auth.dashboard")
        )

    sync_data_plans()

    flash(
        "ClubKonnect plans synced successfully"
    )

    return redirect(
        url_for("admin.admin_data_plans")
    )


@admin_bp.route("/admin/support")
@login_required
@admin_required
def admin_support():
    tickets = SupportTicket.query.order_by(
        SupportTicket.created_at.desc()
    ).all()

    return render_template(
        "admin_support_tickets.html",
        tickets=tickets
    )

@admin_bp.route(
    "/admin/support/<int:ticket_id>",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def admin_support_chat(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        new_status = request.form.get(
            "status",
            ticket.status
        )

        if message:
            admin_message = SupportMessage(
                ticket_id=ticket.id,
                sender_type="admin",
                message=message
            )
            db.session.add(admin_message)

        ticket.status = new_status
        db.session.commit()

        flash("Reply sent successfully.")
        return redirect(
            url_for(
                "admin.admin_support_chat",
                ticket_id=ticket.id
            )
        )

    messages = SupportMessage.query.filter_by(
        ticket_id=ticket.id
    ).order_by(
        SupportMessage.created_at.asc()
    ).all()

    return render_template(
        "admin_support_chat.html",
        ticket=ticket,
        messages=messages
    )

@admin_bp.route("/admin/announcements")
@login_required
@admin_required
def admin_announcements():

    announcements = Announcement.query.order_by(
        Announcement.created_at.desc()
    ).all()

    return render_template(
        "admin/announcements.html",
        announcements=announcements
    )

@admin_bp.route(
    "/announcements/add",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def add_announcement():

    if request.method == "POST":

        title = request.form.get("title", "").strip()

        message = request.form.get("message", "").strip()

        announcement_type = request.form.get(
            "announcement_type",
            "info"
        )

        priority = request.form.get(
            "priority",
            "normal"
        )

        active = True if request.form.get("active") else False

        pinned = True if request.form.get("pinned") else False

        popup = True if request.form.get("popup") else False

        start_date = request.form.get("start_date")

        expiry_date = request.form.get("expiry_date")

        if not title:

            flash("Title is required.", "danger")

            return redirect(
                url_for("admin.add_announcement")
            )

        if not message:

            flash("Message is required.", "danger")

            return redirect(
                url_for("admin.add_announcement")
            )

        announcement = Announcement(

            title=title,

            message=message,

            announcement_type=announcement_type,

            priority=priority,

            active=active,

            pinned=pinned,

            popup=popup,

            created_by=current_user.id

        )

        if start_date:

            announcement.start_date = datetime.strptime(
                start_date,
                "%Y-%m-%dT%H:%M"
            )

        if expiry_date:

            announcement.expiry_date = datetime.strptime(
                expiry_date,
                "%Y-%m-%dT%H:%M"
            )

        db.session.add(announcement)

        db.session.commit()

        users = User.query.all()

        for user in users:

            notification = Notification(

                user_id=user.id,

                title=announcement.title,

                message=announcement.message,

                notification_type="announcement"

            )

            db.session.add(notification)

        db.session.commit()

        flash(
            "Announcement created successfully.",
            "success"
        )

        return redirect(
            url_for("admin.admin_announcements")
        )

    return render_template(
        "admin/add_announcement.html"
    )

@admin_bp.route(
    "/announcements/edit/<int:announcement_id>",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def edit_announcement(announcement_id):

    announcement = Announcement.query.get_or_404(
        announcement_id
    )

    if request.method == "POST":

        announcement.title = request.form.get(
            "title"
        )

        announcement.message = request.form.get(
            "message"
        )

        announcement.announcement_type = request.form.get(
            "announcement_type"
        )

        announcement.priority = request.form.get(
            "priority"
        )

        announcement.active = (
            True if request.form.get("active")
            else False
        )

        announcement.pinned = (
            True if request.form.get("pinned")
            else False
        )

        announcement.popup = (
            True if request.form.get("popup")
            else False
        )

        start_date = request.form.get("start_date")
        expiry_date = request.form.get("expiry_date")

        if start_date:
            announcement.start_date = datetime.strptime(
                start_date,
                "%Y-%m-%dT%H:%M"
            )
        else:
            announcement.start_date = None

        if expiry_date:
            announcement.expiry_date = datetime.strptime(
                expiry_date,
                "%Y-%m-%dT%H:%M"
            )
        else:
            announcement.expiry_date = None

        db.session.commit()

        flash(
            "Announcement updated successfully.",
            "success"
        )

        return redirect(
            url_for("admin.admin_announcements")
        )

    return render_template(
        "admin/edit_announcement.html",
        announcement=announcement
    )

@admin_bp.route(
    "/announcements/delete/<int:announcement_id>"
)
@login_required
@admin_required
def delete_announcement(
    announcement_id
):

    announcement = Announcement.query.get_or_404(
        announcement_id
    )

    db.session.delete(
        announcement
    )

    db.session.commit()

    flash(
        "Announcement deleted.",
        "success"
    )

    return redirect(
        url_for("admin.admin_announcements")
    )

@admin_bp.route(
    "/announcements/toggle/<int:announcement_id>"
)
@login_required
@admin_required
def toggle_announcement(
    announcement_id
):

    announcement = Announcement.query.get_or_404(
        announcement_id
    )

    announcement.active = (
        not announcement.active
    )

    db.session.commit()

    flash(
        "Announcement updated.",
        "success"
    )

    return redirect(
        url_for("admin.admin_announcements")
    )

@admin_bp.route(
    "/announcements/pin/<int:announcement_id>"
)
@login_required
@admin_required
def pin_announcement(
    announcement_id
):

    announcement = Announcement.query.get_or_404(
        announcement_id
    )

    announcement.pinned = (
        not announcement.pinned
    )

    db.session.commit()

    flash(
        "Pin updated.",
        "success"
    )

    return redirect(
        url_for("admin.admin_announcements")
    )
