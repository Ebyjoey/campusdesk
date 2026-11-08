from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLES = ("student", "staff", "admin")
PRIORITIES = ("Low", "Medium", "High")
STATUSES = ("Open", "Assigned", "In Progress", "Resolved", "Closed")

# current status -> statuses it may move to
TRANSITIONS = {
    "Open": {"Assigned"},
    "Assigned": {"In Progress"},
    "In Progress": {"Resolved"},
    "Resolved": {"Closed", "In Progress"},
    "Closed": set(),
}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    default_department = db.Column(db.String(80), default="Facilities")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "default_department": self.default_department,
        }


class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    ticket_no = db.Column(db.String(24), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.String(10), nullable=False, default="Medium")
    status = db.Column(db.String(20), nullable=False, default="Open", index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime)

    category = db.relationship("Category")
    creator = db.relationship("User", foreign_keys=[created_by])
    assignee = db.relationship("User", foreign_keys=[assigned_to])
    comments = db.relationship(
        "Comment", backref="complaint", order_by="Comment.created_at", cascade="all, delete-orphan"
    )
    history = db.relationship(
        "StatusHistory",
        backref="complaint",
        order_by="StatusHistory.changed_at",
        cascade="all, delete-orphan",
    )

    def to_dict(self, detail=False):
        data = {
            "id": self.id,
            "ticket_no": self.ticket_no,
            "title": self.title,
            "description": self.description,
            "category": self.category.name if self.category else None,
            "category_id": self.category_id,
            "location": self.location,
            "priority": self.priority,
            "status": self.status,
            "created_by": self.creator.name if self.creator else None,
            "assigned_to": self.assignee.name if self.assignee else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
        if detail:
            data["comments"] = [c.to_dict() for c in self.comments]
            data["history"] = [h.to_dict() for h in self.history]
        return data


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "user": self.user.name,
            "role": self.user.role,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
        }


class StatusHistory(db.Model):
    __tablename__ = "status_history"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False)
    changed_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user = db.relationship("User")

    def to_dict(self):
        return {
            "old_status": self.old_status,
            "new_status": self.new_status,
            "changed_by": self.user.name,
            "changed_at": self.changed_at.isoformat(),
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
