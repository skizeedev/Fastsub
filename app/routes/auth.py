from datetime import datetime
from functools import wraps

import json
import random
import requests
import secrets
import uuid

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from flask_mail import Message

from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from app import db, mail, oauth

from app.models.user import User
from app.models.transaction import Transaction
from app.models.wallet_transaction import WalletTransaction
from app.models.data_plan import DataPlan
from app.models.notification import Notification
from app.models.support_ticket import SupportTicket
from app.models.support_message import SupportMessage
from app.models.announcement import Announcement

from app.services.paystack import initialize_payment
from app.services.paystack_virtual_account import (
    create_customer,
    create_dedicated_account,
)
from app.services.paystack_dva import create_virtual_account

from app.services.wallet_service import credit_wallet

from app.services.clubkonnect import buy_airtime
from app.services.clubkonnect_data import (
    buy_data,
    buy_data as purchase_data,
)
from app.services.clubkonnect_sync import sync_data_plans
from app.services.clubkonnect_electricity import (
    buy_electricity,
    verify_meter,
)
from app.services.clubkonnect_cable_tv import (
    buy_cable_tv,
    get_cable_tv_packages,
    get_cable_tv_types,
    verify_cable_tv,
)
from app.services.clubkonnect_betting import (
    fund_betting_wallet,
    get_betting_companies,
    verify_betting_customer,
)

NETWORK_CODES = {
    "mtn": "01",
    "glo": "02",
    "9mobile": "03",
    "airtel": "04"
}

DATA_NETWORK_CODES = {
    "mtn": "01",
    "glo": "02",
    "9mobile": "03",
    "airtel": "04"
}

ELECTRICITY_COMPANIES = {
    "01": "Eko Electric - EKEDC",
    "02": "Ikeja Electric - IKEDC",
    "03": "Abuja Electric - AEDC",
    "04": "Kano Electric - KEDC",
    "05": "Port Harcourt Electric - PHEDC",
    "06": "Jos Electric - JEDC",
    "08": "Kaduna Electric - KAEDC",
    "09": "Enugu Electric - EEDC",
    "10": "Benin Electric - BEDC",
    "11": "Yola Electric - YEDC",
    "12": "Aba Electric - APLE",
}

METER_TYPES = {
    "01": "Prepaid",
    "02": "Postpaid"
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

# REGISTER
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        referred_by = request.form.get(
            "referred_by"
        )

        user_exists = User.query.filter_by(email=email).first()

        if user_exists:
            flash("Email already exists")
            return redirect(url_for("auth.register"))

        hashed_password = generate_password_hash(password)

        password = request.form["password"]

        confirm_password = request.form["confirm_password"]

        if password != confirm_password:

            flash(
                "Passwords do not match",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        referral_code = (
            username[:4].upper()
            + str(random.randint(1000, 9999))
        )

        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            referral_code=referral_code,
            referred_by=referred_by
        )

        db.session.add(new_user)
        db.session.commit()

        email_sent = send_verification_email(
            new_user
        )

        if email_sent:

            flash(
                "Account created successfully. Check your email to verify your account.",
                "success"
            )

            return redirect(
                url_for(
                    "auth.verification_page",
                    email=new_user.email
                 )
            )

        else:

            flash(
                "Your account was created, but we could not send the verification email. You can request a new verification email.",
                "warning"
            )

            return redirect(
                url_for(
                    "auth.verification_page",
                    email=new_user.email
                )
            )

    return render_template("auth/register.html")

def reward_referrer(user, amount):

    if not user.referred_by:

        return

    referrer = User.query.filter_by(
        referral_code=user.referred_by
    ).first()

    if not referrer:

        return

    commission = amount * 0.02

    referrer.wallet_balance += commission

    referrer.referral_earnings = (
        referrer.referral_earnings or 0
    ) + commission

@auth_bp.route("/google-callback")
def google_callback():

    try:
        # ==========================================
        # 1. GET GOOGLE ACCESS TOKEN
        # ==========================================

        token = oauth.google.authorize_access_token()

        user_info = token.get("userinfo")

        if not user_info:
            flash(
                "Unable to get information from Google.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        # ==========================================
        # 2. GET GOOGLE USER INFORMATION
        # ==========================================

        google_id = user_info.get("sub")
        email = user_info.get("email")

        first_name = user_info.get(
            "given_name",
            ""
        )

        last_name = user_info.get(
            "family_name",
            ""
        )

        name = user_info.get(
            "name",
            ""
        )

        profile_picture = user_info.get(
            "picture"
        )


        if not google_id or not email:

            flash(
                "Google did not provide the required account information.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )


        # ==========================================
        # 3. CHECK IF GOOGLE ACCOUNT ALREADY EXISTS
        # ==========================================

        user = User.query.filter_by(
            google_id=google_id
        ).first()


        # ==========================================
        # 4. IF GOOGLE ID DOES NOT EXIST,
        #    CHECK EMAIL
        # ==========================================

        if not user:

            user = User.query.filter_by(
                email=email
            ).first()


        # ==========================================
        # 5. EXISTING USER
        # ==========================================

        if user:

            # --------------------------------------
            # Link Google account if not linked
            # --------------------------------------

            if not user.google_id:

                user.google_id = google_id


            # --------------------------------------
            # Mark authentication provider
            # --------------------------------------

            user.auth_provider = "google"


            # --------------------------------------
            # Google already verified the email
            # --------------------------------------

            user.is_verified = True


            # --------------------------------------
            # Update first name if missing
            # --------------------------------------

            if not user.first_name:

                user.first_name = first_name


            # --------------------------------------
            # Update last name if missing
            # --------------------------------------

            if not user.last_name:

                user.last_name = last_name


            # --------------------------------------
            # Add profile picture if missing
            # --------------------------------------

            if not user.profile_picture:

                user.profile_picture = profile_picture


            db.session.commit()


            # --------------------------------------
            # Login user
            # --------------------------------------

            login_user(user)


            flash(
                "Welcome back!",
                "success"
            )

            return redirect(
                url_for("auth.dashboard")
            )


        # ==========================================
        # 6. CREATE NEW GOOGLE USER
        # ==========================================

        username = (
            name.strip()
            if name
            else email.split("@")[0]
        )


        # ==========================================
        # 7. MAKE USERNAME UNIQUE
        # ==========================================

        original_username = username

        counter = 1

        while User.query.filter_by(
            username=username
        ).first():

            username = (
                f"{original_username}{counter}"
            )

            counter += 1


        # ==========================================
        # 8. GENERATE RANDOM PASSWORD
        # ==========================================

        random_password = secrets.token_urlsafe(
            32
        )


        # ==========================================
        # 9. GENERATE UNIQUE REFERRAL CODE
        # ==========================================

        referral_code = (
            username[:4].upper()
            + str(
                secrets.randbelow(
                    9000
                ) + 1000
            )
        )


        # ==========================================
        # 10. CREATE USER
        # ==========================================

        new_user = User(

            username=username,

            email=email,

            password_hash=generate_password_hash(
                random_password
            ),

            google_id=google_id,

            auth_provider="google",

            is_verified=True,

            first_name=first_name,

            last_name=last_name,

            profile_picture=profile_picture,

            referral_code=referral_code

        )


        db.session.add(
            new_user
        )

        db.session.commit()


        # ==========================================
        # 11. CREATE PAYSTACK CUSTOMER
        # ==========================================

        try:

            from app.services.paystack import (
                create_customer,
                create_dedicated_account
            )


            customer = create_customer(

                email=new_user.email,

                first_name=new_user.first_name
                or new_user.username,

                last_name=new_user.last_name
                or ""

            )


            if customer:

                new_user.paystack_customer_code = (
                    customer.get(
                        "customer_code"
                    )
                )

                if customer.get("id"):

                    new_user.paystack_customer_id = (
                        str(
                            customer.get(
                                "id"
                            )
                        )
                    )

                # ==================================
                # CREATE DEDICATED VIRTUAL ACCOUNT
                # ==================================

                account = create_dedicated_account(

                    customer.get(
                        "customer_code"
                    )

                )


                if account:

                    new_user.paystack_dedicated_account_id = (
                        str(account.get("id"))
                        if account.get("id")
                        else None
                    )

                    new_user.virtual_account_number = (
                        account.get("account_number")
                    )

                    new_user.virtual_account_name = (
                        account.get("account_name")
                    )

                    new_user.virtual_bank_name = (
                        account.get("bank", {}).get("name")
                    )

                    new_user.virtual_account_reference = (
                        account.get("account_reference")
                    )



                db.session.commit()


        except Exception as e:

            print(
                "PAYSTACK GOOGLE REGISTRATION ERROR:",
                e
            )

            # Do NOT delete the user.
            #
            # Google registration succeeded.
            # Paystack can be completed later.


        # ==========================================
        # 12. LOGIN NEW GOOGLE USER
        # ==========================================

        login_user(
            new_user
        )


        flash(
            "Google account created successfully. Welcome to FastSub!",
            "success"
        )


        return redirect(
            url_for("auth.dashboard")
        )


    except Exception as e:

        # ==========================================
        # 13. GENERAL GOOGLE LOGIN ERROR
        # ==========================================

        db.session.rollback()

        print(
            "GOOGLE LOGIN ERROR:",
            e
        )

        flash(
            "Unable to complete Google login. Please try again.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

# LOGIN
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(
            email=email
        ).first()

        if not user or not check_password_hash(
            user.password_hash,
            password
        ):
            flash("Invalid credentials")
            return redirect(
                url_for("auth.login")
            )

        if not user.is_active_user:

            flash("Account suspended")

            return redirect(
                url_for("auth.login")
            )

        if not user.is_verified:

            flash(
                "Please verify your email before logging in.",
                "warning"
            )

            return redirect(
                url_for(
                    "auth.verification_page",
                    email=email
                 )
            )


        login_user(user)

        next_page = request.args.get("next")

        if next_page:
            return redirect(next_page)

        flash("Login successful")

        return redirect(
            url_for("auth.dashboard")
        )

    return render_template(
        "auth/login.html"
    )

@auth_bp.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        user = User.query.filter_by(
            email=email
        ).first()

        # Do not reveal whether an email exists
        if user:

            try:

                send_password_reset_email(
                    user
                )

                print(
                    f"PASSWORD RESET EMAIL SENT TO {email}"
                )

            except Exception as e:

                print(
                    "PASSWORD RESET EMAIL ERROR:",
                    e
                )

        flash(
            "If an account exists with that email, "
            "you will receive a password reset link shortly.",
            "info"
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    return render_template(
        "auth/forgot_password.html"
    )

@auth_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    email = verify_password_reset_token(
        token
    )

    if not email:

        flash(
            "This password reset link is invalid or has expired.",
            "danger"
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    user = User.query.filter_by(
        email=email
    ).first()

    if not user:

        flash(
            "This password reset link is invalid.",
            "danger"
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    if request.method == "POST":

        password = request.form.get(
            "password"
        )

        confirm_password = request.form.get(
            "confirm_password"
        )

        if not password or not confirm_password:

            flash(
                "Please fill in all password fields.",
                "danger"
            )

            return render_template(
                "auth/reset_password.html"
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return render_template(
                "auth/reset_password.html"
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "danger"
            )

            return render_template(
                "auth/reset_password.html"
            )

        user.password_hash = (
            generate_password_hash(
                password
            )
        )

        db.session.commit()

        flash(
            "Your password has been reset successfully. You can now log in.",
            "success"
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    return render_template(
        "auth/reset_password.html"
    )

@auth_bp.route("/google-login")
def google_login():

    redirect_uri = url_for(
        "auth.google_callback",
        _external=True
    )

    return oauth.google.authorize_redirect(
        redirect_uri
    )

#VERIFICATION
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def generate_verification_token(email):

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    return serializer.dumps(
        email,
        salt="email-verification"
    )

def send_verification_email(user):

    token = generate_verification_token(
        user.email
    )

    verify_link = url_for(
        "auth.verify_email",
        token=token,
        _external=True
    )

    msg = Message(
        subject="Verify Your FastSub Account",
        recipients=[user.email]
    )

    msg.body = f"""
Welcome to FastSub!

Thank you for creating your account.

Please click the link below to verify your email:

{verify_link}

This verification link will expire in 24 hours.

If you did not create this account,
you can safely ignore this email.

FastSub.ng
"""

    try:

        mail.send(msg)

        user.verification_email_sent_at = (
            datetime.utcnow()
        )

        db.session.commit()

        print(
            f"VERIFICATION EMAIL SENT TO {user.email}"
        )

        return True

    except Exception as e:

        print(
            f"VERIFICATION EMAIL ERROR: {e}"
        )

        return False


def generate_password_reset_token(email):

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    return serializer.dumps(
        email,
        salt="password-reset"
    )


def verify_password_reset_token(token):

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    try:

        email = serializer.loads(
            token,
            salt="password-reset",
            max_age=3600
        )

        return email

    except (
        SignatureExpired,
        BadSignature
    ):

        return None

def send_password_reset_email(user):

    token = generate_password_reset_token(
        user.email
    )

    reset_link = url_for(
        "auth.reset_password",
        token=token,
        _external=True
    )

    msg = Message(
        subject="Reset Your FastSub Password",
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipients=[user.email]
    )

    msg.body = f"""
Hello {user.username},

We received a request to reset your FastSub password.

Click the link below to create a new password:

{reset_link}

This link will expire in 1 hour.

If you did not request a password reset,
you can safely ignore this email.

FastSub Team
"""

    mail.send(msg)

@auth_bp.route("/verify-email/<token>")
def verify_email(token):

    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"]
    )

    try:

        email = serializer.loads(
            token,
            salt="email-verification",
            max_age=86400
        )

    except (
        SignatureExpired,
        BadSignature
    ):

        flash(
            "Your verification link is invalid or has expired.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    user = User.query.filter_by(
        email=email
    ).first()


    if not user:

        flash(
            "User account not found.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )


    if user.is_verified:

        flash(
            "Your email has already been verified.",
            "info"
        )

        return redirect(
            url_for("auth.login")
        )


    # Mark email as verified
    user.is_verified = True

    db.session.commit()


    # Create Paystack customer and dedicated account
    try:

        from app.services.paystack import (
            create_customer,
            create_dedicated_account
        )


        if not user.paystack_customer_code:

            customer = create_customer(
                email=user.email,
                first_name=user.username,
                last_name=""
            )


            if customer:

                user.paystack_customer_code = (
                    customer.get("customer_code")
                )

                user.paystack_customer_id = (
                    customer.get("id")
                )

                user.customer_code = (
                    customer.get("customer_code")
                )


                if user.paystack_customer_code:

                    account = create_dedicated_account(
                        user.paystack_customer_code
                    )


                    if account:

                        user.paystack_dedicated_account_id = (
                            str(account.get("id"))
                            if account.get("id")
                            else None
                        )

                        user.virtual_account_name = (
                            account.get("account_name")
                        )

                        user.virtual_account_number = (
                            account.get("account_number")
                        )

                        user.virtual_bank_name = (
                            account.get("bank", {}).get("name")
                        )

                        user.virtual_account_reference = (
                            account.get("account_reference")
                        )


        db.session.commit()


    except Exception as e:

        print(
            "PAYSTACK ACCOUNT CREATION ERROR:",
            e
        )

        db.session.rollback()


    flash(
        "Email verified successfully! You can now log in.",
        "success"
    )


    return redirect(
        url_for("auth.login")
    )

@auth_bp.route(
    "/verify-email",
    methods=["GET"]
)
def verification_page():

    email = request.args.get("email")

    if not email:

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "auth/verify_email.html",
        email=email
    )

@auth_bp.route(
    "/resend-verification",
    methods=["GET", "POST"]
)
def resend_verification():

    # Get email from either:
    # /resend-verification?email=example@gmail.com
    # or a POST form
    email = request.args.get("email")

    if request.method == "POST":
        email = request.form.get("email")

    if not email:
        flash(
            "Please enter your email address.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    # Find user
    user = User.query.filter_by(
        email=email
    ).first()

    # Don't reveal whether an email exists
    if not user:

        flash(
            "If an account exists with that email, "
            "a verification email will be sent.",
            "info"
        )

        return redirect(
            url_for("auth.login")
        )

    # Already verified
    if user.is_verified:

        flash(
            "This account is already verified. "
            "You can log in.",
            "info"
        )

        return redirect(
            url_for("auth.login")
        )

    # =========================
    # 60 SECOND COOLDOWN
    # =========================

    if user.verification_email_sent_at:

        elapsed = (
            datetime.utcnow()
            - user.verification_email_sent_at
        ).total_seconds()

        if elapsed < 60:

            remaining = int(
                60 - elapsed
            )

            flash(
                f"Please wait {remaining} seconds "
                "before requesting another verification email.",
                "warning"
            )

            return redirect(
                url_for("auth.login")
            )

    # =========================
    # SEND VERIFICATION EMAIL
    # =========================

    try:

        send_verification_email(user)

        user.verification_email_sent_at = (
            datetime.utcnow()
        )

        db.session.commit()

        flash(
            "A new verification email has been sent. "
            "Please check your inbox.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            "RESEND VERIFICATION ERROR:",
            e
        )

        flash(
            "We could not send the verification email. "
            "Please try again later.",
            "danger"
        )

    return redirect(
        url_for("auth.login")
    )


# DASHBOARD
@auth_bp.route("/dashboard")
@login_required
def dashboard():

    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.created_at.desc()
    ).limit(5).all()

    total_spent = current_user.total_spent or 0

    wallet = current_user.wallet_balance or 0

    referral = current_user.referral_earnings or 0

    announcement = Announcement.query.filter(
        Announcement.active == True,
        db.or_(
            Announcement.start_date == None,
            Announcement.start_date <= datetime.utcnow()
        ),
        db.or_(
            Announcement.expiry_date == None,
            Announcement.expiry_date >= datetime.utcnow()
        )
    ).order_by(
        Announcement.pinned.desc(),
        Announcement.created_at.desc()
    ).first()

    return render_template(
        "dashboard/home.html",
        recent_transactions=recent_transactions,
        wallet=wallet,
        total_spent=total_spent,
        referral=referral,
        announcement=announcement,
        user=current_user
    )

#ANNOUNCEMENT
@auth_bp.route("/announcements")
@login_required
def announcements():

    announcements = Announcement.query.filter(
        Announcement.active == True
    ).order_by(
        Announcement.created_at.desc()
    ).all()

    return render_template(
        "announcements.html",
        announcements=announcements
    )

#COMING SOON
@auth_bp.route("/coming-soon")
@login_required
def coming_soon():

    return render_template(
        "dashboard/coming_soon.html"
    )

#PROFILLE
@auth_bp.route("/profile")
@login_required
def profile():

    return render_template(
        "dashboard/profile.html"
    )

#SUPPORT
@auth_bp.route("/support", methods=["GET", "POST"])
@login_required
def support():
    if request.method == "POST":
        subject = request.form.get("subject")
        message = request.form.get("message")

        if not subject or not message:
            flash("Subject and message are required.")
            return redirect(url_for("auth.support"))

        ticket = SupportTicket(
            user_id=current_user.id,
            subject=subject,
            status="open"
        )
        db.session.add(ticket)
        db.session.flush()  # gets ticket.id before commit

        first_message = SupportMessage(
            ticket_id=ticket.id,
            sender_type="user",
            message=message
        )
        db.session.add(first_message)
        db.session.commit()

        flash("Support ticket created successfully.")
        return redirect(url_for("auth.support"))

    tickets = SupportTicket.query.filter_by(
        user_id=current_user.id
    ).order_by(
        SupportTicket.created_at.desc()
    ).all()

    support_email = "fastsub.ngofficial@gmail.com"
    support_phone = "+2349021306863"

    return render_template(
        "support.html",
        tickets=tickets,
        support_email=support_email,
        support_phone=support_phone
    )

@auth_bp.route(
    "/support/new",
    methods=["GET", "POST"]
)
@login_required
def new_ticket():

    if request.method == "POST":

        subject = request.form.get(
            "subject"
        )

        message = request.form.get(
            "message"
        )

        ticket = SupportTicket(
            user_id=current_user.id,
            subject=subject
        )

        db.session.add(ticket)
        db.session.flush()

        first_message = SupportMessage(
            ticket_id=ticket.id,
            sender_type="user",
            message=message
        )

        db.session.add(
            first_message
        )

        db.session.commit()

        flash(
            "Ticket created successfully"
        )

        return redirect(
            url_for(
                "auth.ticket_detail",
                ticket_id=ticket.id
            )
        )

    return render_template(
        "new_ticket.html"
    )

@auth_bp.route("/support/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def support_ticket_chat(ticket_id):
    ticket = SupportTicket.query.filter_by(
        id=ticket_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        message = request.form.get("message")

        if not message:
            flash("Message cannot be empty.")
            return redirect(
                url_for(
                    "auth.support_ticket_chat",
                    ticket_id=ticket.id
                )
            )

        new_message = SupportMessage(
            ticket_id=ticket.id,
            sender_type="user",
            message=message
        )

        db.session.add(new_message)
        db.session.commit()

        flash("Reply sent successfully.")
        return redirect(
            url_for(
                "auth.support_ticket_chat",
                ticket_id=ticket.id
            )
        )

    messages = SupportMessage.query.filter_by(
        ticket_id=ticket.id
    ).order_by(
        SupportMessage.created_at.asc()
    ).all()

    return render_template(
        "support_ticket_chat.html",
        ticket=ticket,
        messages=messages
    )

#FUND WALLET

@auth_bp.route("/fund-wallet/paystack")
@login_required
def fund_wallet_paystack():

    amount = float(request.args.get("amount"))

    paystack_response = initialize_payment(
        email=current_user.email,
        amount=amount,
        callback_url=url_for(
            "auth.verify_payment",
            _external=True
        )
    )

    print("KEY =", current_app.config.get("PAYSTACK_SECRET_KEY"))
    print("RESPONSE =", paystack_response)

    if paystack_response.get("status"):

        return redirect(
            paystack_response["data"]["authorization_url"]
        )

    print("PAYSTACK KEY:")
    print(current_app.config["PAYSTACK_SECRET_KEY"])

    flash("Payment initialization failed")
    return redirect(url_for("auth.fund_wallet"))


@auth_bp.route("/fund-wallet", methods=["GET", "POST"])
@login_required
def fund_wallet():

    if request.method == "POST":

        amount = float(request.form.get("amount"))

        # store in session for preview step
        session["fund_amount"] = amount
        session["fund_reference"] = str(uuid.uuid4())

        return redirect(url_for("auth.fund_wallet_preview"))

    if not current_user.virtual_account_number:

        customer = create_customer(current_user)

        if customer.get("status"):

            current_user.paystack_customer_code = customer["data"]["customer_code"]
            current_user.paystack_customer_id = str(customer["data"]["id"])

            account = create_dedicated_account(
                current_user.paystack_customer_code
            )

            if account.get("status"):

                data = account["data"]

                current_user.virtual_account_number = data["account_number"]
                current_user.virtual_account_name = data["account_name"]
                current_user.virtual_bank_name = data["bank"]["name"]
                current_user.virtual_account_reference = data["reference"]
                current_user.paystack_dedicated_account_id = str(data["id"])

                db.session.commit()

    return render_template("dashboard/fund_wallet.html")


@auth_bp.route("/verify-payment")
@login_required
def verify_payment():

    reference = request.args.get("reference")

    existing = Transaction.query.filter_by(
        reference=reference
    ).first()

    if existing:
        flash("Payment already processed")
        return redirect(url_for("auth.dashboard"))


    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}"
    }

    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers=headers
    )

    data = response.json()

    if (
        data["status"] and
        data["data"]["status"] == "success"
    ):

        amount = data["data"]["amount"] / 100

        credit_wallet(current_user, amount)

        transaction = Transaction(
            user_id=current_user.id,
            service_type="wallet_funding",
            amount=amount,
            recipient="Paystack",
            status="success",
            reference=reference
        )

        notification = Notification(
            user_id=current_user.id,
            title="Wallet Funded",
            message=f"₦{amount:,.2f} has been added to your wallet.",
            notification_type="wallet"
        )

        db.session.add(notification)
        db.session.add(transaction)
        db.session.commit()

        flash("Wallet funded successfully!")

        return redirect(url_for("auth.dashboard"))

@auth_bp.route("/fund-wallet/preview", methods=["GET", "POST"])
@login_required
def fund_wallet_preview():

    amount = session.get("fund_amount")
    reference = session.get("fund_reference")

    if not amount:
        return redirect(url_for("auth.fund_wallet"))

    if request.method == "POST":

        transaction = Transaction(
            user_id=current_user.id,
            service_type="wallet_funding",
            amount=amount,
            recipient="Paystack",
            status="pending",
            reference=reference
        )

        db.session.add(transaction)
        db.session.commit()

        return redirect(
            url_for(
                "auth.fund_wallet_paystack",
                amount=amount,
                reference=reference
            )
        )

    return render_template(
        "dashboard/fund_preview.html",
        amount=amount,
        reference=reference
    )

@auth_bp.route("/generate-account")
@login_required
def generate_account():

    if current_user.account_number:
        flash("Account already exists.")
        return redirect(url_for("auth.wallet"))

    from app.services.paystack_dva import create_virtual_account

    account = create_virtual_account(current_user)

    current_user.bank_name = account["bank_name"]
    current_user.account_name = account["account_name"]
    current_user.account_number = account["account_number"]
    current_user.customer_code = account["customer_code"]
    current_user.paystack_customer_id = str(account["customer_id"])

    db.session.commit()

    flash("Virtual account created successfully.")

    return redirect(url_for("auth.wallet"))

@auth_bp.route("/generate-pva")
@login_required
def generate_pva():

    if current_user.account_number:
        flash("Virtual account already exists.")
        return redirect(url_for("auth.wallet"))

    customer = create_customer(
        email=current_user.email,
        first_name=current_user.username,
        last_name=""
    )

    account = create_dedicated_account(
        customer["customer_code"]
    )

    current_user.customer_code = customer["customer_code"]
    current_user.paystack_customer_code = customer["customer_code"]
    current_user.paystack_customer_id = customer["id"]

    current_user.account_name = account["account_name"]
    current_user.account_number = account["account_number"]
    current_user.bank_name = account["bank"]["name"]

    db.session.commit()

    flash("Virtual account generated successfully.")

    return redirect(url_for("auth.wallet"))

#NOTIFICATION
@auth_bp.route("/notifications")
@login_required
def notifications():

    notifications = Notification.query.filter_by(

        user_id=current_user.id

    ).order_by(

        Notification.created_at.desc()

    ).all()

    return render_template(

        "dashboard/notifications.html",

        notifications=notifications

    )

@auth_bp.route("/notification/read/<int:notification_id>")
@login_required
def read_notification(notification_id):

    notifications = Notification.query.filter_by(

        id=notification_id,

        user_id=current_user.id

    ).first_or_404()

    Notification.is_read = True

    db.session.commit()

    return redirect(url_for("auth.notifications"))


@auth_bp.route("/notifications/read-all")
@login_required
def read_all_notifications():

    Notification.query.filter_by(

        user_id=current_user.id,

        is_read=False

    ).update({

        "is_read": True

    })

    db.session.commit()

    flash("All notifications marked as read.")

    return redirect(url_for("auth.notifications"))




#TRANSACTION
@auth_bp.route("/transactions")
@login_required
def transactions():

    search = request.args.get(
        "search",
        ""
    )

    service = request.args.get(
        "service",
        ""
    )

    query = Transaction.query.filter_by(
        user_id=current_user.id
    )

    if search:

        query = query.filter(
            Transaction.recipient.contains(search)
        )

    if service:

        query = query.filter(
            Transaction.service_type.contains(service)
        )

    transactions = query.order_by(Transaction.created_at.desc()).all()

    total_transactions = len(transactions)

    successful_transactions = sum(
        1 for t in transactions if t.status == "success"
    )

    pending_transactions = sum(
        1 for t in transactions if t.status == "pending"
    )

    failed_transactions = sum(
        1 for t in transactions if t.status == "failed"
    )

    return render_template(
        "dashboard/transactions.html",
        transactions=transactions,
        total_transactions=total_transactions,
        successful_transactions=successful_transactions,
        pending_transactions=pending_transactions,
        failed_transactions=failed_transactions
    )

#RECEIPT
@auth_bp.route("/receipt/<int:transaction_id>")
@login_required
def receipt(transaction_id):

    transaction = Transaction.query.get_or_404(transaction_id)

    if transaction.user_id != current_user.id:
        abort(403)

    return render_template(
        "dashboard/receipt.html",
        transaction=transaction
    )

#WALLET HISTORY
@auth_bp.route("/wallet-history")
@login_required
def wallet_history():

    transactions = WalletTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        WalletTransaction.created_at.desc()
    ).all()

    return render_template(
        "dashboard/wallet_history.html",
        transactions=transactions
    )

#SERVICES
@auth_bp.route("/data", methods=["GET", "POST"])
@login_required
def buy_data_page():

    networks = DataPlan.query.with_entities(
        DataPlan.network
    ).distinct().all()

    plans = DataPlan.query.filter_by(
        active=True
    ).order_by(
        DataPlan.selling_price.asc()
    ).all()

    if request.method == "POST":

        plan_id = request.form.get("plan")
        phone = request.form.get("phone")

        plan = DataPlan.query.get_or_404(
            plan_id
        )

        return render_template(
            "services/data_preview.html",
            plan=plan,
            phone=phone
        )

    return render_template(
        "services/data.html",
        networks=networks,
        plans=plans
    )


@auth_bp.route(
    "/confirm-data",
    methods=["POST"]
)
@login_required
def confirm_data():

    plan_id = request.form.get(
        "plan_id"
    )

    phone = request.form.get(
        "phone"
    )

    plan = DataPlan.query.get_or_404(
        plan_id
    )

    if (
        current_user.wallet_balance
        < plan.selling_price
    ):

        flash(
            "Insufficient wallet balance"
        )

        return redirect(
            url_for("auth.buy_data_page")
        )

    reference = str(
        uuid.uuid4()
    )[:12]

    transaction = Transaction(
        user_id=current_user.id,
        service_type="data",
        amount=plan.selling_price,
        recipient=phone,
        status="pending",
        reference=reference
    )

    notification = Notification(
        user_id=current_user.id,
        title="Data Purchase Successful",
        message=f"{plan.plan_name} has been delivered successfully.",
        notification_type="transaction"
    )

    db.session.add(notification)

    existing = Transaction.query.filter_by(
        reference=reference
    ).first()

    if existing:

        flash("Duplicate transaction detected.")

        return redirect(url_for("auth.dashboard"))



    db.session.add(
        transaction
    )

    current_user.wallet_balance -= (
        plan.selling_price
    )

    db.session.commit()

    print(purchase_data)
    print(type(purchase_data))
    print(
        plan.network_code,
        plan.provider_plan_id,
        plan.plan_name
    )

    if not plan.provider_plan_id:

        current_user.wallet_balance += plan.selling_price

        transaction.status = "failed"

        db.session.commit()

        flash(
            "Plan not properly configured."
        )

        return redirect(
           url_for("auth.buy_data_page")
        )


    try:

        response = purchase_data(
            network=plan.network_code,
            data_plan=plan.provider_plan_id,
            phone=phone,
            request_id=reference
        )

        transaction.provider_reference = response.get(
            "orderid"
        )

        print(response)

        if response.get("status") == "ORDER_RECEIVED":

            transaction.status = (
                "success"
            )

            transaction.provider_reference = (
                response.get("orderid")
            )


            db.session.commit()

            flash(
                "Data purchase successful"
            )

        elif response.get("status") == "INVALID_DATAPLAN":

           current_user.wallet_balance += plan.selling_price

           transaction.status = "failed"

           db.session.commit()

           flash(
               "Invalid data plan. Wallet refunded."
           )

        else:

            current_user.wallet_balance += (
                plan.selling_price
            )

            transaction.status = (
                "failed"
            )

            db.session.commit()

            flash(
                "Purchase failed. Wallet refunded."
            )

    except Exception as e:

        import traceback

        traceback.print_exc()

        current_user.wallet_balance += (
            plan.selling_price
        )

        transaction.status = (
            "failed"
        )

        db.session.commit()

        print(e)

        flash(
            "Network error. Wallet refunded."
        )

    return redirect(
        url_for(
            "auth.receipt",
            transaction_id=transaction.id
        )
    )



@auth_bp.route("/airtime", methods=["GET", "POST"])
@login_required
def airtime():

    if request.method == "POST":

        network = request.form.get("network")
        phone = request.form.get("phone")
        amount = float(request.form.get("amount"))

        return render_template(
            "services/airtime_preview.html",
            network=network,
            phone=phone,
            amount=amount
        )

    return render_template(
        "services/airtime.html"
    )

@auth_bp.route("/airtime/confirm", methods=["POST"])
@login_required
def confirm_airtime():

    network = request.form.get("network")
    phone = request.form.get("phone")

    try:
        amount = float(request.form.get("amount"))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("auth.airtime"))

    if current_user.wallet_balance < amount:
        flash("Insufficient wallet balance")
        return redirect(url_for("auth.airtime"))

    network_code = NETWORK_CODES.get(network.lower())

    if not network_code:
        flash("Invalid network selected")
        return redirect(url_for("auth.airtime"))

    reference = str(uuid.uuid4()).replace("-", "")[:12]

    if Transaction.query.filter_by(reference=reference).first():
        flash("Duplicate transaction detected.")
        return redirect(url_for("auth.dashboard"))

    transaction = Transaction(
        user_id=current_user.id,
        service_type="airtime",
        network=network.upper(),
        amount=amount,
        recipient=phone,
        product_name=f"{network.upper()} Airtime",
        description=f"{network.upper()} Airtime Purchase",
        status="pending",
        reference=reference
    )

    notification = Notification(
        user_id=current_user.id,
        title="Airtime Purchase",
        message="Your airtime purchase was successful.",
        notification_type="transaction"
    )

    db.session.add(notification)
    db.session.add(transaction)

    current_user.wallet_balance -= amount

    db.session.commit()

    try:

        response = buy_airtime(
            network=network_code,
            amount=amount,
            phone=phone,
            request_id=reference
        )

        print("AIRTIME RESPONSE:", response)

        transaction.provider_reference = (
            response.get("orderid")
            or response.get("OrderID")
        )

        transaction.provider_status = (
            response.get("status")
        )

        transaction.provider_response = str(response)

        success_statuses = [
            "ORDER_RECEIVED",
            "SUCCESS",
            "success",
            "00"
        ]

        if response.get("status") in success_statuses:

            transaction.status = "success"

            current_user.total_spent = (
                current_user.total_spent or 0
            ) + amount

            reward_referrer(
                current_user,
                amount
            )

            db.session.commit()

            flash("Airtime purchase successful")

        else:

            current_user.wallet_balance += amount

            transaction.status = "failed"

            db.session.commit()

            flash("Airtime purchase failed. Wallet refunded.")

    except Exception as e:

        current_user.wallet_balance += amount

        transaction.status = "failed"

        transaction.provider_response = str(e)

        db.session.commit()

        flash("Network error. Wallet refunded.")

    return redirect(
        url_for(
            "auth.receipt",
            transaction_id=transaction.id
        )
    )


@auth_bp.route("/electricity", methods=["GET"])
@login_required
def electricity_page():
    return render_template(
        "services/electricity.html",
        companies=ELECTRICITY_COMPANIES,
        meter_types=METER_TYPES
    )

@auth_bp.route("/verify-electricity", methods=["POST"])
@login_required
def verify_electricity():
    electric_company = request.form.get("electric_company")
    meter_type = request.form.get("meter_type")
    meter_no = request.form.get("meter_no")
    amount = request.form.get("amount")
    phone = request.form.get("phone")

    if not electric_company or not meter_type or not meter_no or not amount or not phone:
        flash("Please fill all electricity details.")
        return redirect(url_for("auth.electricity_page"))

    try:
        # USE YOUR EXISTING FUNCTION NAME HERE
        verification = verify_meter(
            electric_company=electric_company,
            meter_no=meter_no,
            meter_type=meter_type
        )

        print("VERIFY RESPONSE:", verification)

        # If provider did not verify meter successfully
        if verification.get("status") != "00":
            flash("Unable to verify meter details. Please check the meter number and try again.")
            return redirect(url_for("auth.electricity_page"))

        customer_name = verification.get("customer_name", "N/A")

        electric_company_names = {
            "01": "Eko Electric - EKEDC",
            "02": "Ikeja Electric - IKEDC",
            "03": "Abuja Electric - AEDC",
            "04": "Kano Electric - KEDC",
            "05": "Portharcourt Electric - PHEDC",
            "06": "Jos Electric - JEDC",
            "08": "Kaduna Electric - KAEDC",
            "09": "Enugu Electric - EEDC",
            "10": "Benin Electric - BEDC",
            "11": "Yola Electric - YEDC",
            "12": "Aba Electric - APLE",
        }

        meter_type_names = {
            "01": "Prepaid",
            "02": "Postpaid"
        }

        # Optional: keep verified data in session for confirm step
        session["electricity_verification"] = {
            "electric_company": electric_company,
            "meter_type": meter_type,
            "meter_no": meter_no,
            "amount": amount,
            "phone": phone,
            "customer_name": customer_name
        }

        return render_template(
            "services/confirm_electricity.html",
            electric_company_code=electric_company,
            electric_company_name=electric_company_names.get(electric_company, electric_company),
            meter_type_code=meter_type,
            meter_type_name=meter_type_names.get(meter_type, meter_type),
            meter_no=meter_no,
            amount=amount,
            phone=phone,
            customer_name=customer_name,
            verification_status="Verified successfully"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(e)

        flash("Unable to verify meter right now.")
        return redirect(url_for("auth.electricity_page"))


@auth_bp.route("/confirm-electricity", methods=["POST"])
@login_required
def confirm_electricity():
    electric_company = request.form.get("electric_company")
    meter_type = request.form.get("meter_type")
    meter_no = request.form.get("meter_no")
    phone = request.form.get("phone")
    customer_name = request.form.get("customer_name")

    try:
        amount = float(request.form.get("amount"))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("auth.electricity_page"))

    if not all([electric_company, meter_type, meter_no, phone, customer_name]):
        flash("Missing electricity payment details.")
        return redirect(url_for("auth.electricity_page"))

    if current_user.wallet_balance < amount:
        flash("Insufficient wallet balance")
        return redirect(url_for("auth.electricity_page"))

    electric_company_names = {
        "01": "Eko Electric - EKEDC",
        "02": "Ikeja Electric - IKEDC",
        "03": "Abuja Electric - AEDC",
        "04": "Kano Electric - KEDC",
        "05": "Portharcourt Electric - PHEDC",
        "06": "Jos Electric - JEDC",
        "08": "Kaduna Electric - KAEDC",
        "09": "Enugu Electric - EEDC",
        "10": "Benin Electric - BEDC",
        "11": "Yola Electric - YEDC",
        "12": "Aba Electric - APLE",
    }

    meter_type_names = {
        "01": "Prepaid",
        "02": "Postpaid"
    }

    reference = str(uuid.uuid4())[:12]

    existing = Transaction.query.filter_by(
        reference=reference
    ).first()

    if existing:

        flash("Duplicate transaction detected.")

        return redirect(url_for("auth.dashboard"))



    transaction = Transaction(
        user_id=current_user.id,
        service_type="electricity",
        amount=amount,
        recipient=meter_no,
        status="pending",
        reference=reference,
        description=f"{electric_company_names.get(electric_company, electric_company)} electricity purchase",
        customer_name=customer_name,
        electric_company_code=electric_company,
        electric_company_name=electric_company_names.get(electric_company, electric_company),
        meter_number=meter_no,
        meter_type=meter_type_names.get(meter_type, meter_type)
    )

    notification = Notification(
        user_id=current_user.id,
        title="Electricity Purchased",
        message=f"Token: {token}",
        notification_type="electricity"
    )

    db.session.add(notification)
    db.session.add(transaction)
    current_user.wallet_balance -= amount
    db.session.commit()

    try:
        response = buy_electricity(
            electric_company=electric_company,
            meter_type=meter_type,
            meter_no=meter_no,
            amount=amount,
            phone=phone,
            request_id=reference
        )

        print("ELECTRICITY PURCHASE RESPONSE:", response)

        transaction.provider_reference = response.get("orderid")
        transaction.provider_status = response.get("status")
        transaction.provider_response = str(response)

        # token / units if returned by provider
        transaction.token = (
            response.get("token")
            or response.get("Token")
            or response.get("TOKEN")
        )

        transaction.units = (
            response.get("units")
            or response.get("Units")
            or response.get("UNITS")
        )

        success_statuses = ["ORDER_RECEIVED", "success", "Successful", "00"]

        if response.get("status") in success_statuses:
            transaction.status = "success"
            db.session.commit()
            flash("Electricity payment successful")
        else:
            current_user.wallet_balance += amount
            transaction.status = "failed"
            db.session.commit()
            flash("Electricity payment failed. Wallet refunded.")

    except Exception as e:
        import traceback
        traceback.print_exc()

        current_user.wallet_balance += amount
        transaction.status = "failed"
        transaction.provider_response = str(e)
        db.session.commit()

        flash("Network error. Wallet refunded.")

    return redirect(
                url_for(
                    "auth.receipt",
                    transaction_id=transaction.id
                )
            )



@auth_bp.route("/cable-tv", methods=["GET"])
@login_required
def cable_tv_page():
    try:
        cable_types_response = get_cable_tv_types()
        cable_packages_response = get_cable_tv_packages()

        print("CABLE TYPES RESPONSE:", cable_types_response)
        print("CABLE PACKAGES RESPONSE:", cable_packages_response)

        # =========================================================
        # 1) NORMALIZE PROVIDERS
        # =========================================================
        providers = {}

        # Support list response directly
        if isinstance(cable_types_response, list):
            for item in cable_types_response:
                provider_id = (
                    item.get("TV_ID")
                    or item.get("tv_id")
                    or item.get("id")
                    or item.get("ID")
                )
                provider_name = (
                    item.get("TV_NAME")
                    or item.get("tv_name")
                    or item.get("name")
                    or item.get("NAME")
                )

                if provider_id and provider_name:
                    providers[str(provider_id)] = provider_name

        # Support dict response
        elif isinstance(cable_types_response, dict):
            possible_provider_lists = [
                cable_types_response.get("CABLE_TV"),
                cable_types_response.get("cable_tv"),
                cable_types_response.get("providers"),
                cable_types_response.get("data"),
            ]

            for provider_list in possible_provider_lists:
                if isinstance(provider_list, list):
                    for item in provider_list:
                        provider_id = (
                            item.get("TV_ID")
                            or item.get("tv_id")
                            or item.get("id")
                            or item.get("ID")
                        )
                        provider_name = (
                            item.get("TV_NAME")
                            or item.get("tv_name")
                            or item.get("name")
                            or item.get("NAME")
                        )

                        if provider_id and provider_name:
                            providers[str(provider_id)] = provider_name

        # =========================================================
        # 2) NORMALIZE PACKAGES
        # Final format we want:
        # {
        #   "01": [
        #       {
        #           "package_id": "123",
        #           "package_name": "DStv Compact",
        #           "amount": 15000
        #       }
        #   ]
        # }
        # =========================================================
        packages_by_provider = {}

        def add_package(provider_id, package_id, package_name, amount):
            if not provider_id or not package_id or not package_name:
                return

            provider_id = str(provider_id)

            try:
                amount = float(amount)
            except (TypeError, ValueError):
                amount = 0

            if provider_id not in packages_by_provider:
                packages_by_provider[provider_id] = []

            packages_by_provider[provider_id].append({
                "package_id": str(package_id),
                "package_name": str(package_name),
                "amount": amount
            })

        # ---------------------------------------------------------
        # CASE A: package response is dict
        # ---------------------------------------------------------
        if isinstance(cable_packages_response, dict):

            # ---------- FORMAT 1 ----------
            # {
            #   "TV_ID": {
            #       "1": [
            #           {
            #               "ID": "01",
            #               "PRODUCT": [...]
            #           }
            #       ]
            #   }
            # }
            raw_tv_data = cable_packages_response.get("TV_ID")

            if isinstance(raw_tv_data, dict):
                for _, provider_blocks in raw_tv_data.items():
                    if not isinstance(provider_blocks, list):
                        continue

                    for block in provider_blocks:
                        provider_id = (
                            block.get("ID")
                            or block.get("TV_ID")
                            or block.get("provider_id")
                        )

                        product_list = (
                            block.get("PRODUCT")
                            or block.get("products")
                            or block.get("PACKAGES")
                            or []
                        )

                        if not provider_id or not isinstance(product_list, list):
                            continue

                        for product in product_list:
                            package_id = (
                                product.get("PACKAGE_ID")
                                or product.get("package_id")
                                or product.get("id")
                                or product.get("ID")
                            )
                            package_name = (
                                product.get("PACKAGE_NAME")
                                or product.get("package_name")
                                or product.get("name")
                                or product.get("PRODUCT_NAME")
                            )
                            amount = (
                                product.get("PACKAGE_AMOUNT")
                                or product.get("amount")
                                or product.get("price")
                            )

                            add_package(provider_id, package_id, package_name, amount)

            # ---------- FORMAT 2 ----------
            # {
            #   "packages": [
            #       {
            #           "provider_id": "01",
            #           "package_id": "123",
            #           "package_name": "DStv Compact",
            #           "amount": "15000"
            #       }
            #   ]
            # }
            possible_package_lists = [
                cable_packages_response.get("packages"),
                cable_packages_response.get("PACKAGES"),
                cable_packages_response.get("data"),
                cable_packages_response.get("PRODUCT"),
            ]

            for package_list in possible_package_lists:
                if isinstance(package_list, list):
                    for product in package_list:
                        provider_id = (
                            product.get("provider_id")
                            or product.get("TV_ID")
                            or product.get("cable_tv")
                            or product.get("ID")
                        )
                        package_id = (
                            product.get("PACKAGE_ID")
                            or product.get("package_id")
                            or product.get("id")
                            or product.get("ID")
                        )
                        package_name = (
                            product.get("PACKAGE_NAME")
                            or product.get("package_name")
                            or product.get("name")
                            or product.get("PRODUCT_NAME")
                        )
                        amount = (
                            product.get("PACKAGE_AMOUNT")
                            or product.get("amount")
                            or product.get("price")
                        )

                        add_package(provider_id, package_id, package_name, amount)

        # ---------------------------------------------------------
        # CASE B: package response is already a list
        # ---------------------------------------------------------
        elif isinstance(cable_packages_response, list):
            for product in cable_packages_response:
                provider_id = (
                    product.get("provider_id")
                    or product.get("TV_ID")
                    or product.get("cable_tv")
                    or product.get("ID")
                )
                package_id = (
                    product.get("PACKAGE_ID")
                    or product.get("package_id")
                    or product.get("id")
                    or product.get("ID")
                )
                package_name = (
                    product.get("PACKAGE_NAME")
                    or product.get("package_name")
                    or product.get("name")
                    or product.get("PRODUCT_NAME")
                )
                amount = (
                    product.get("PACKAGE_AMOUNT")
                    or product.get("amount")
                    or product.get("price")
                )

                add_package(provider_id, package_id, package_name, amount)

        # Remove providers with empty package lists if needed
        for provider_id in list(packages_by_provider.keys()):
            if not packages_by_provider[provider_id]:
                del packages_by_provider[provider_id]

        print("NORMALIZED PROVIDERS:", providers)
        print("NORMALIZED PACKAGES:", packages_by_provider)

        return render_template(
            "services/cable_tv.html",
            providers=providers,
            packages_by_provider=packages_by_provider
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("CABLE PAGE ERROR:", e)

        flash("Unable to load cable TV providers right now.")
        return render_template(
            "services/cable_tv.html",
            providers={},
            packages_by_provider={}
        )


@auth_bp.route("/verify-cable-tv", methods=["POST"])
@login_required
def verify_cable_tv_route():
    cable_tv = request.form.get("cable_tv", "").strip()
    package_code = request.form.get("package", "").strip()
    smartcard_no = request.form.get("smartcard_no", "").strip()
    phone = request.form.get("phone", "").strip()



    if not cable_tv or not package_code or not smartcard_no or not phone:
        flash("Please fill all cable TV details.")
        return redirect(url_for("auth.cable_tv_page"))

    try:
        # -----------------------------------------
        # Reload provider/package data so we can
        # find package name + amount from package code
        # -----------------------------------------
        cable_types_response = get_cable_tv_types()
        cable_packages_response = get_cable_tv_packages()

        # Build providers map
        providers = {}
        cable_type_list = cable_types_response.get("CABLE_TV", [])
        if isinstance(cable_type_list, list):
            for item in cable_type_list:
                provider_code = str(item.get("TV_ID", "")).strip()
                provider_name = str(item.get("TV_NAME", "")).strip()
                if provider_code and provider_name:
                    providers[provider_code] = provider_name

        # Build packages map again
        packages_by_provider = {}

        raw = cable_packages_response.get("TV_ID", {})

        for _, blocks in raw.items():

            if not isinstance(blocks, list):
                continue

            for block in blocks:

                provider_id = block.get("ID")

                if not provider_id:
                    continue

                products = []

                for product in block.get("PRODUCT", []):

                    products.append({
                        "package_id": product["PACKAGE_ID"],
                        "package_name": product["PACKAGE_NAME"],
                        "amount": float(product["PACKAGE_AMOUNT"])
                    })

                packages_by_provider[provider_id] = products

        # -----------------------------------------
        # Find selected provider name
        # -----------------------------------------
        cable_tv_name = providers.get(cable_tv, cable_tv)

        print("=" * 60)
        print("Provider selected:", cable_tv)
        print("Package selected:", package_code)

        print("Available providers:")
        print(packages_by_provider.keys())

        print("Packages under this provider:")
        print(packages_by_provider.get(cable_tv))

        print("=" * 60)

        # -----------------------------------------
        # Find selected package details
        # -----------------------------------------
        selected_package = None
        provider_packages = packages_by_provider.get(cable_tv, [])

        for pkg in provider_packages:
            if str(pkg.get("package_id")) == package_code:
                selected_package = pkg
                break

        if not selected_package:
            flash("Selected package could not be found. Please try again.")
            return redirect(url_for("auth.cable_tv_page"))

        package_name = selected_package["package_name"]
        amount = selected_package["amount"]

        # -----------------------------------------
        # Verify smartcard/IUC
        # -----------------------------------------
        verification = verify_cable_tv(
            cable_tv=cable_tv,
            smartcard_no=smartcard_no
        )

        print("CABLE VERIFY RESPONSE:", verification)

        response_status = str(
            verification.get("status")
            or verification.get("Status")
            or ""
        ).strip()

        customer_name = (
            verification.get("customer_name")
            or verification.get("Customer_Name")
            or verification.get("name")
            or verification.get("Name")
            or "N/A"
        )

        success_statuses = ["00", "success", "SUCCESS", "ORDER_RECEIVED"]

        if response_status not in success_statuses:
            flash("Unable to verify smartcard/IUC number. Please check and try again.")
            return redirect(url_for("auth.cable_tv_page"))

        return render_template(
            "services/confirm_cable_tv.html",
            cable_tv_code=cable_tv,
            cable_tv_name=cable_tv_name,
            package_code=package_code,
            package_name=package_name,
            smartcard_no=smartcard_no,
            phone=phone,
            amount=amount,
            customer_name=customer_name,
            verification_status="Verified successfully"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("VERIFY CABLE ERROR:", e)

        flash("Unable to verify smartcard right now.")
        return redirect(url_for("auth.cable_tv_page"))


@auth_bp.route("/confirm-cable-tv", methods=["POST"])
@login_required
def confirm_cable_tv():
    cable_tv = request.form.get("cable_tv", "").strip()
    cable_tv_name = request.form.get("cable_tv_name", "").strip()
    package_code = request.form.get("package_code", "").strip()
    package_name = request.form.get("package_name", "").strip()
    smartcard_no = request.form.get("smartcard_no", "").strip()
    phone = request.form.get("phone", "").strip()
    customer_name = request.form.get("customer_name", "").strip()

    try:
        amount = float(request.form.get("amount", 0))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("auth.cable_tv_page"))

    if not cable_tv or not package_code or not smartcard_no or not phone or amount <= 0:
        flash("Missing cable TV details.")
        return redirect(url_for("auth.cable_tv_page"))

    if current_user.wallet_balance < amount:
        flash("Insufficient wallet balance")
        return redirect(url_for("auth.cable_tv_page"))

    reference = str(uuid.uuid4())[:12]

    transaction = Transaction(
        user_id=current_user.id,
        service_type="cable_tv",
        amount=amount,
        recipient=smartcard_no,
        status="pending",
        reference=reference,
        description=f"{cable_tv_name} subscription - {package_name}",
        product_name=package_name,
        customer_name=customer_name,

        # cable details
        cable_tv_code=cable_tv,
        cable_tv_name=cable_tv_name,
        package_code=package_code,
        package_name=package_name,
        smartcard_number=smartcard_no
    )

    existing = Transaction.query.filter_by(
        reference=reference
    ).first()

    if existing:

        flash("Duplicate transaction detected.")

        return redirect(url_for("auth.dashboard"))

    notification = Notification(
        user_id=current_user.id,
        title="Cable Subscription",
        message="Your subscription was renewed.",
        notification_type="cable"
    )

    db.session.add(notification)
    db.session.add(transaction)
    current_user.wallet_balance -= amount
    db.session.commit()

    try:
        response = buy_cable_tv(
            cable_tv=cable_tv,
            package=package_code,
            smartcard_no=smartcard_no,
            phone=phone,
            request_id=reference
        )

        print("CABLE PURCHASE RESPONSE:", response)

        response_status = str(
            response.get("status")
            or response.get("Status")
            or ""
        ).strip()

        transaction.provider_reference = (
            response.get("orderid")
            or response.get("OrderID")
        )
        transaction.provider_status = response_status
        transaction.provider_response = str(response)

        success_statuses = [
            "ORDER_RECEIVED",
            "success",
            "Successful",
            "SUCCESS",
            "00"
        ]

        if response_status in success_statuses:
            transaction.status = "success"
            db.session.commit()
            flash("Cable TV subscription successful")
        else:
            current_user.wallet_balance += amount
            transaction.status = "failed"
            db.session.commit()
            flash("Cable TV subscription failed. Wallet refunded.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("CONFIRM CABLE ERROR:", e)

        current_user.wallet_balance += amount
        transaction.status = "failed"
        transaction.provider_response = str(e)
        db.session.commit()

        flash("Network error. Wallet refunded.")

    return redirect(
                url_for(
                    "auth.receipt",
                    transaction_id=transaction.id
                )
            )



@auth_bp.route("/betting", methods=["GET"])
@login_required
def betting_page():
    try:
        response = get_betting_companies()

        print("BETTING RESPONSE:", response)

        companies = {}

        for item in response.get("BETTING_COMPANY", []):
            code = str(item.get("PRODUCT_CODE", "")).strip()
            name = str(item.get("PRODUCT_NAME", "")).strip()

            if code and name:
                companies[code] = {
                    "name": name,
                    "min": float(item.get("MINAMOUNT", 100)),
                    "max": float(item.get("MAXAMOUNT", 50000))
                }

        print("NORMALIZED BETTING:", companies)

        return render_template(
            "services/betting.html",
            companies=companies
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("BETTING PAGE ERROR:", e)

        flash("Unable to load betting companies.")

        return render_template(
            "services/betting.html",
            companies={}
        )


@auth_bp.route("/verify-betting", methods=["POST"])
@login_required
def verify_betting():

    betting_company = request.form.get("betting_company", "").strip()
    betting_company_name = request.form.get("betting_company_name", "").strip()
    customer_id = request.form.get("customer_id", "").strip()
    phone = request.form.get("phone", "").strip()

    try:
        amount = float(request.form.get("amount", 0))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("auth.betting_page"))

    if not betting_company or not customer_id or not phone or amount <= 0:
        flash("Please complete all fields.")
        return redirect(url_for("auth.betting_page"))

    try:

        response = verify_betting_customer(
            betting_company=betting_company,
            customer_id=customer_id
        )

        print("VERIFY BETTING RESPONSE:", response)

        status = str(
            response.get("status")
            or response.get("Status")
            or ""
        ).strip()

        customer_name = (
            response.get("customer_name")
            or response.get("Customer_Name")
            or response.get("name")
            or response.get("Name")
            or "N/A"
        )

        success_status = [
            "00",
            "SUCCESS",
            "success",
            "ORDER_RECEIVED"
        ]

        if status not in success_status:
            flash("Customer ID could not be verified.")
            return redirect(url_for("auth.betting_page"))

        return render_template(
            "services/confirm_betting.html",
            betting_company=betting_company,
            betting_company_name=betting_company_name,
            customer_id=customer_id,
            customer_name=customer_name,
            phone=phone,
            amount=amount,
            verification_status="Verified Successfully"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()

        print("VERIFY BETTING ERROR:", e)

        flash("Unable to verify customer.")

        return redirect(url_for("auth.betting_page"))


@auth_bp.route("/confirm-betting", methods=["POST"])
@login_required
def confirm_betting():

    betting_company = request.form.get("betting_company", "").strip()
    betting_company_name = request.form.get("betting_company_name", "").strip()
    customer_id = request.form.get("customer_id", "").strip()
    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()

    try:
        amount = float(request.form.get("amount", 0))
    except (TypeError, ValueError):
        flash("Invalid amount.")
        return redirect(url_for("auth.betting_page"))

    if (
        not betting_company
        or not customer_id
        or not phone
        or amount <= 0
    ):
        flash("Missing betting details.")
        return redirect(url_for("auth.betting_page"))

    if current_user.wallet_balance < amount:
        flash("Insufficient wallet balance.")
        return redirect(url_for("auth.betting_page"))

    reference = str(uuid.uuid4())[:12]

    transaction = Transaction(
        user_id=current_user.id,
        service_type="betting",
        amount=amount,
        recipient=customer_id,
        status="pending",
        reference=reference,
        description=f"{betting_company_name} Wallet Funding",
        customer_name=customer_name,
        product_name=betting_company_name,
        betting_company_code=betting_company,
        betting_company_name=betting_company_name,
    )

    existing = Transaction.query.filter_by(
        reference=reference
    ).first()

    if existing:

        flash("Duplicate transaction detected.")

        return redirect(url_for("auth.dashboard"))

    notification = Notification(
        user_id=current_user.id,
        title="Bet Wallet Funded",
        message="Your betting wallet has been funded.",
        notification_type="betting"
    )

    db.session.add(notification)
    db.session.add(transaction)

    current_user.wallet_balance -= amount

    db.session.commit()

    try:

        response = fund_betting_wallet(
            betting_company=betting_company,
            customer_id=customer_id,
            amount=amount,
            phone=phone,
            request_id=reference
        )

        print("BETTING PURCHASE RESPONSE:", response)

        response_status = str(
            response.get("status")
            or response.get("Status")
            or ""
        ).strip()

        transaction.provider_reference = (
            response.get("orderid")
            or response.get("OrderID")
        )

        transaction.provider_status = response_status

        transaction.provider_response = str(response)

        success_status = [
            "00",
            "SUCCESS",
            "success",
            "Successful",
            "ORDER_RECEIVED"
        ]

        if response_status in success_status:

            transaction.status = "success"

            db.session.commit()

            flash("Betting wallet funded successfully.")

        else:

            current_user.wallet_balance += amount

            transaction.status = "failed"

            db.session.commit()

            flash("Betting funding failed. Wallet refunded.")

    except Exception as e:

        import traceback
        traceback.print_exc()

        print("BETTING ERROR:", e)

        current_user.wallet_balance += amount

        transaction.status = "failed"

        transaction.provider_response = str(e)

        db.session.commit()

        flash("Network error. Wallet refunded.")

    return redirect(
                url_for(
                    "auth.receipt",
                    transaction_id=transaction.id
                )
            )



# UPDATE WALLET
@auth_bp.route("/update_wallet")
@login_required
def update_wallet(user, amount, mode="spend"):
    if user.total_spent is None:
        user.total_spent = 0

    if user.total_funded is None:
        user.total_funded = 0

    if mode == "spend":
        user.total_spent += amount

    elif mode == "fund":
        user.total_funded += amount

    user.wallet_balance = (user.total_funded - user.total_spent)


# LOGOUT
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully")
    return redirect(url_for("auth.login"))
