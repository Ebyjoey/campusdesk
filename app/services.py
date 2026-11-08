"""Business rules shared by the JSON API and the HTML pages."""
import re
from collections import Counter as PyCounter
from datetime import datetime

from .extensions import db
from .metrics import COMPLAINTS_CREATED
from .models import (
    PRIORITIES,
    STATUSES,
    TRANSITIONS,
    Category,
    Comment,
    Complaint,
    StatusHistory,
    User,
    utcnow,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ServiceError(Exception):
    """Raised with an HTTP-style status code and a human message."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _clean(value):
    return value.strip() if isinstance(value, str) else ""


def register_user(name, email, password):
    name, email = _clean(name), _clean(email).lower()
    if not 2 <= len(name) <= 80:
        raise ServiceError("Name must be 2-80 characters.")
    if not EMAIL_RE.match(email) or len(email) > 120:
        raise ServiceError("Enter a valid email address.")
    if not isinstance(password, str) or len(password) < 8:
        raise ServiceError("Password must be at least 8 characters.")
    if User.query.filter_by(email=email).first():
        raise ServiceError("That email is already registered.", 409)
    user = User(name=name, email=email, role="student")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def can_view(user, complaint):
    if user.role == "admin":
        return True
    if user.role == "student":
        return complaint.created_by == user.id
    return complaint.assigned_to == user.id


def visible_complaints(user, status=None, category_id=None, priority=None, mine=False):
    q = Complaint.query
    if user.role == "student":
        q = q.filter(Complaint.created_by == user.id)
    elif user.role == "staff":
        q = q.filter(Complaint.assigned_to == user.id)
    elif mine:
        q = q.filter((Complaint.created_by == user.id) | (Complaint.assigned_to == user.id))
    if status:
        q = q.filter(Complaint.status == status)
    if category_id:
        q = q.filter(Complaint.category_id == category_id)
    if priority:
        q = q.filter(Complaint.priority == priority)
    return q.order_by(Complaint.created_at.desc())


def create_complaint(user, title, description, category_id, location, priority):
    title, description, location = _clean(title), _clean(description), _clean(location)
    if not 5 <= len(title) <= 120:
        raise ServiceError("Title must be 5-120 characters.")
    if not 10 <= len(description) <= 2000:
        raise ServiceError("Description must be 10-2000 characters.")
    if not 2 <= len(location) <= 120:
        raise ServiceError("Location must be 2-120 characters.")
    if priority not in PRIORITIES:
        raise ServiceError("Priority must be Low, Medium or High.")
    category = db.session.get(Category, category_id) if isinstance(category_id, int) else None
    if category is None:
        raise ServiceError("Choose a valid category.")

    complaint = Complaint(
        ticket_no=f"TMP-{datetime.now().timestamp()}",
        title=title,
        description=description,
        category_id=category.id,
        location=location,
        priority=priority,
        status="Open",
        created_by=user.id,
    )
    db.session.add(complaint)
    db.session.flush()
    complaint.ticket_no = f"CD-{utcnow().year}-{complaint.id:05d}"
    db.session.add(
        StatusHistory(complaint_id=complaint.id, changed_by=user.id, old_status=None, new_status="Open")
    )
    db.session.commit()
    COMPLAINTS_CREATED.labels(category.name).inc()
    return complaint


def edit_complaint(user, complaint, title=None, description=None, location=None):
    if complaint.created_by != user.id:
        raise ServiceError("Only the owner can edit this complaint.", 403)
    if complaint.status != "Open":
        raise ServiceError("Only Open complaints can be edited.", 409)
    if title is not None:
        title = _clean(title)
        if not 5 <= len(title) <= 120:
            raise ServiceError("Title must be 5-120 characters.")
        complaint.title = title
    if description is not None:
        description = _clean(description)
        if not 10 <= len(description) <= 2000:
            raise ServiceError("Description must be 10-2000 characters.")
        complaint.description = description
    if location is not None:
        location = _clean(location)
        if not 2 <= len(location) <= 120:
            raise ServiceError("Location must be 2-120 characters.")
        complaint.location = location
    db.session.commit()
    return complaint


def _record(complaint, user, old, new):
    db.session.add(
        StatusHistory(complaint_id=complaint.id, changed_by=user.id, old_status=old, new_status=new)
    )


def assign_complaint(admin, complaint, staff_id):
    if admin.role != "admin":
        raise ServiceError("Only admins can assign complaints.", 403)
    staff = db.session.get(User, staff_id) if isinstance(staff_id, int) else None
    if staff is None or staff.role != "staff":
        raise ServiceError("Choose a valid staff member.")
    if complaint.status not in ("Open", "Assigned"):
        raise ServiceError("Only Open or Assigned complaints can be (re)assigned.", 409)
    old = complaint.status
    complaint.assigned_to = staff.id
    complaint.status = "Assigned"
    _record(complaint, admin, old, "Assigned")
    db.session.commit()
    return complaint


def change_status(user, complaint, new_status):
    if new_status not in STATUSES:
        raise ServiceError("Unknown status.")
    old = complaint.status
    if new_status not in TRANSITIONS[old]:
        raise ServiceError(f"Cannot move from {old} to {new_status}.", 409)

    is_admin = user.role == "admin"
    is_assignee = complaint.assigned_to == user.id
    is_owner = complaint.created_by == user.id
    if old == "Assigned" and new_status == "In Progress":
        allowed = is_admin or is_assignee
    elif old == "In Progress" and new_status == "Resolved":
        allowed = is_admin or is_assignee
    else:  # Resolved -> Closed, Resolved -> In Progress (reopen)
        allowed = is_admin or is_owner
    if not allowed:
        raise ServiceError("You are not allowed to make this change.", 403)

    complaint.status = new_status
    if new_status == "Resolved":
        complaint.resolved_at = utcnow()
    elif old == "Resolved" and new_status == "In Progress":
        complaint.resolved_at = None
    _record(complaint, user, old, new_status)
    db.session.commit()
    return complaint


def add_comment(user, complaint, body):
    body = _clean(body)
    if not 1 <= len(body) <= 1000:
        raise ServiceError("Comment must be 1-1000 characters.")
    comment = Comment(complaint_id=complaint.id, user_id=user.id, body=body)
    db.session.add(comment)
    db.session.commit()
    return comment


def add_category(name, department):
    name, department = _clean(name), _clean(department) or "Facilities"
    if not 2 <= len(name) <= 60:
        raise ServiceError("Category name must be 2-60 characters.")
    if Category.query.filter(db.func.lower(Category.name) == name.lower()).first():
        raise ServiceError("That category already exists.", 409)
    category = Category(name=name, default_department=department[:80])
    db.session.add(category)
    db.session.commit()
    return category


def delete_category(category):
    if Complaint.query.filter_by(category_id=category.id).first():
        raise ServiceError("Category is in use by complaints.", 409)
    db.session.delete(category)
    db.session.commit()


def stats_summary(user):
    q = visible_complaints(user)
    complaints = q.all()
    by_status = PyCounter({s: 0 for s in STATUSES})
    by_category = PyCounter()
    durations = []
    for c in complaints:
        by_status[c.status] += 1
        by_category[c.category.name] += 1
        if c.resolved_at:
            durations.append((c.resolved_at - c.created_at).total_seconds() / 3600)
    avg = round(sum(durations) / len(durations), 2) if durations else None
    return {
        "total": len(complaints),
        "by_status": dict(by_status),
        "by_category": dict(by_category),
        "avg_resolution_hours": avg,
    }
