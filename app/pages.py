"""Server-rendered pages plus health and metrics endpoints."""
from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy import text
from wtforms import PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length

from . import services as svc
from .extensions import db, limiter
from .metrics import LOGIN_FAILURES, render_metrics
from .models import PRIORITIES, STATUSES, Category, Complaint, User

bp = Blueprint("main", __name__)


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(2, 80)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 128)])


class ComplaintForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(5, 120)])
    category_id = SelectField("Category", coerce=int)
    location = StringField("Location", validators=[DataRequired(), Length(2, 120)])
    priority = SelectField("Priority", choices=[(p, p) for p in PRIORITIES], default="Medium")
    description = TextAreaField("Description", validators=[DataRequired(), Length(10, 2000)])


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(2, 60)])
    default_department = StringField("Default department", validators=[Length(0, 80)])


class EmptyForm(FlaskForm):
    """Used only for its CSRF token on small POST buttons."""


# ---------- health and metrics ----------
@bp.get("/healthz")
def healthz():
    return jsonify(status="ok")


@bp.get("/readyz")
def readyz():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means not ready
        return jsonify(status="database unavailable"), 503
    return jsonify(status="ready")


@bp.get("/metrics")
def metrics():
    payload, content_type = render_metrics(db, Complaint, STATUSES)
    return Response(payload, mimetype=content_type)


# ---------- auth pages ----------
@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login_page():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(request.args.get("next") or url_for("main.dashboard"))
        LOGIN_FAILURES.inc()
        flash("Invalid email or password.", "danger")
    return render_template("login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def register_page():
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            svc.register_user(form.name.data, form.email.data, form.password.data)
        except svc.ServiceError as err:
            flash(err.message, "danger")
        else:
            flash("Account created. Please sign in.", "success")
            return redirect(url_for("main.login_page"))
    return render_template("register.html", form=form)


@bp.post("/logout")
@login_required
def logout_page():
    logout_user()
    return redirect(url_for("main.index"))


# ---------- app pages ----------
@bp.get("/dashboard")
@login_required
def dashboard():
    recent = svc.visible_complaints(current_user).limit(5).all()
    return render_template(
        "dashboard.html", stats=svc.stats_summary(current_user), recent=recent
    )


@bp.get("/complaints")
@login_required
def complaints_page():
    complaints = svc.visible_complaints(
        current_user,
        status=request.args.get("status") or None,
        category_id=request.args.get("category", type=int),
        priority=request.args.get("priority") or None,
        mine=request.args.get("mine") in ("1", "true"),
    ).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "complaints.html",
        complaints=complaints,
        categories=categories,
        statuses=STATUSES,
        priorities=PRIORITIES,
    )


@bp.route("/complaints/new", methods=["GET", "POST"])
@login_required
def complaint_new():
    if current_user.role != "student":
        abort(403)
    form = ComplaintForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name)]
    if form.validate_on_submit():
        try:
            complaint = svc.create_complaint(
                current_user,
                form.title.data,
                form.description.data,
                form.category_id.data,
                form.location.data,
                form.priority.data,
            )
        except svc.ServiceError as err:
            flash(err.message, "danger")
        else:
            flash(f"Complaint {complaint.ticket_no} raised.", "success")
            return redirect(url_for("main.complaint_detail", complaint_id=complaint.id))
    return render_template("complaint_new.html", form=form)


@bp.get("/complaints/<int:complaint_id>")
@login_required
def complaint_detail(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None or not svc.can_view(current_user, complaint):
        abort(404)
    staff = User.query.filter_by(role="staff").order_by(User.name).all() if current_user.role == "admin" else []
    return render_template(
        "complaint_detail.html", c=complaint, staff=staff, statuses=STATUSES
    )


@bp.route("/admin/categories", methods=["GET", "POST"])
@login_required
def admin_categories():
    if current_user.role != "admin":
        abort(403)
    form = CategoryForm()
    delete_form = EmptyForm()
    if form.validate_on_submit():
        try:
            svc.add_category(form.name.data, form.default_department.data)
        except svc.ServiceError as err:
            flash(err.message, "danger")
        else:
            flash("Category added.", "success")
            return redirect(url_for("main.admin_categories"))
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "categories.html", form=form, delete_form=delete_form, categories=categories
    )


@bp.post("/admin/categories/<int:category_id>/delete")
@login_required
def admin_category_delete(category_id):
    if current_user.role != "admin":
        abort(403)
    category = db.session.get(Category, category_id)
    if category is None:
        abort(404)
    try:
        svc.delete_category(category)
    except svc.ServiceError as err:
        flash(err.message, "danger")
    else:
        flash("Category removed.", "success")
    return redirect(url_for("main.admin_categories"))
