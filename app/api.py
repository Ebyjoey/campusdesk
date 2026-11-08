"""JSON API (/api/...)."""
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_user, logout_user

from . import services as svc
from .extensions import csrf, db, limiter
from .metrics import LOGIN_FAILURES
from .models import Category, Complaint, User

bp = Blueprint("api", __name__, url_prefix="/api")


def roles_required(*roles):
    """Signed-in user, optionally restricted to the given roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify(error="Authentication required."), 401
            if roles and current_user.role not in roles:
                return jsonify(error="You do not have permission."), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@bp.errorhandler(svc.ServiceError)
def handle_service_error(err):
    return jsonify(error=err.message), err.status


def body():
    return request.get_json(silent=True) or {}


def get_visible_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None or not svc.can_view(current_user, complaint):
        # 404 for both cases so ticket ids cannot be probed
        raise svc.ServiceError("Complaint not found.", 404)
    return complaint


# ---------- auth ----------
@bp.post("/auth/register")
@csrf.exempt
@limiter.limit("10 per minute")
def register():
    data = body()
    user = svc.register_user(data.get("name"), data.get("email"), data.get("password"))
    return jsonify(user.to_dict()), 201


@bp.post("/auth/login")
@csrf.exempt
@limiter.limit("10 per minute")
def login():
    data = body()
    email = (data.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(data.get("password") or ""):
        LOGIN_FAILURES.inc()
        return jsonify(error="Invalid email or password."), 401
    login_user(user)
    return jsonify(user.to_dict())


@bp.post("/auth/logout")
@roles_required()
def logout():
    logout_user()
    return jsonify(message="Signed out.")


@bp.get("/auth/me")
@roles_required()
def me():
    return jsonify(current_user.to_dict())


# ---------- complaints ----------
@bp.get("/complaints")
@roles_required()
def list_complaints():
    q = svc.visible_complaints(
        current_user,
        status=request.args.get("status"),
        category_id=request.args.get("category", type=int),
        priority=request.args.get("priority"),
        mine=request.args.get("mine") in ("1", "true"),
    )
    return jsonify([c.to_dict() for c in q.all()])


@bp.post("/complaints")
@roles_required("student")
def create_complaint():
    d = body()
    complaint = svc.create_complaint(
        current_user,
        d.get("title"),
        d.get("description"),
        d.get("category_id"),
        d.get("location"),
        d.get("priority", "Medium"),
    )
    return jsonify(complaint.to_dict(detail=True)), 201


@bp.get("/complaints/<int:complaint_id>")
@roles_required()
def get_complaint(complaint_id):
    return jsonify(get_visible_complaint(complaint_id).to_dict(detail=True))


@bp.put("/complaints/<int:complaint_id>")
@roles_required("student")
def edit_complaint(complaint_id):
    complaint = get_visible_complaint(complaint_id)
    d = body()
    svc.edit_complaint(
        current_user, complaint, d.get("title"), d.get("description"), d.get("location")
    )
    return jsonify(complaint.to_dict(detail=True))


@bp.delete("/complaints/<int:complaint_id>")
@roles_required("admin")
def delete_complaint(complaint_id):
    complaint = get_visible_complaint(complaint_id)
    db.session.delete(complaint)
    db.session.commit()
    return jsonify(message="Deleted.")


@bp.patch("/complaints/<int:complaint_id>/assign")
@roles_required("admin")
def assign(complaint_id):
    complaint = get_visible_complaint(complaint_id)
    svc.assign_complaint(current_user, complaint, body().get("staff_id"))
    return jsonify(complaint.to_dict(detail=True))


@bp.patch("/complaints/<int:complaint_id>/status")
@roles_required()
def set_status(complaint_id):
    complaint = get_visible_complaint(complaint_id)
    svc.change_status(current_user, complaint, body().get("status"))
    return jsonify(complaint.to_dict(detail=True))


@bp.route("/complaints/<int:complaint_id>/comments", methods=["GET", "POST"])
@roles_required()
def comments(complaint_id):
    complaint = get_visible_complaint(complaint_id)
    if request.method == "POST":
        comment = svc.add_comment(current_user, complaint, body().get("body"))
        return jsonify(comment.to_dict()), 201
    return jsonify([c.to_dict() for c in complaint.comments])


# ---------- categories, users, stats ----------
@bp.get("/categories")
@roles_required()
def list_categories():
    return jsonify([c.to_dict() for c in Category.query.order_by(Category.name).all()])


@bp.post("/categories")
@roles_required("admin")
def create_category():
    d = body()
    category = svc.add_category(d.get("name"), d.get("default_department"))
    return jsonify(category.to_dict()), 201


@bp.delete("/categories/<int:category_id>")
@roles_required("admin")
def remove_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        raise svc.ServiceError("Category not found.", 404)
    svc.delete_category(category)
    return jsonify(message="Deleted.")


@bp.get("/users")
@roles_required("admin")
def list_users():
    role = request.args.get("role")
    q = User.query
    if role:
        q = q.filter_by(role=role)
    return jsonify([u.to_dict() for u in q.order_by(User.name).all()])


@bp.get("/stats/summary")
@roles_required("admin", "staff", "student")
def stats():
    return jsonify(svc.stats_summary(current_user))
