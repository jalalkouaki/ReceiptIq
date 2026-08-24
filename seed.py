from models import User, ExpenseCategory
from auth import hash_password
from config import load_settings
from logger import log_event

BUILTIN_CATEGORIES = [
    {"name": "Meals", "slug": "meals", "tax_deductible": True, "color": "#ffc107"},
    {"name": "Software & Subscriptions", "slug": "software-subscriptions", "tax_deductible": True, "color": "#0d6efd"},
    {"name": "Travel", "slug": "travel", "tax_deductible": True, "color": "#6f42c1"},
    {"name": "Office Supplies", "slug": "office-supplies", "tax_deductible": True, "color": "#198754"},
    {"name": "Utilities", "slug": "utilities", "tax_deductible": True, "color": "#0dcaf0"},
    {"name": "Marketing", "slug": "marketing", "tax_deductible": True, "color": "#fd7e14"},
    {"name": "Groceries", "slug": "groceries", "tax_deductible": False, "color": "#20c997"},
    {"name": "Other", "slug": "other", "tax_deductible": False, "color": "#6c757d"},
]


def seed_database(session):
    """Seed default admin user and built-in expense categories. NO DUMMY DATA."""
    cfg = load_settings()
    admin_user = cfg.get("DEFAULT_ADMIN_USER", "admin")
    admin_pass = cfg.get("DEFAULT_ADMIN_PASSWORD", "admin123")

    # 1. Seed categories
    for cat_data in BUILTIN_CATEGORIES:
        existing = session.query(ExpenseCategory).filter_by(slug=cat_data["slug"]).first()
        if not existing:
            cat = ExpenseCategory(**cat_data)
            session.add(cat)

    # 2. Seed admin user if not exists
    admin = session.query(User).filter_by(username=admin_user).first()
    if not admin:
        new_admin = User(
            username=admin_user,
            password_hash=hash_password(admin_pass),
            role="admin",
            must_change_password=True if admin_pass == "admin123" else False
        )
        session.add(new_admin)
        log_event("admin", f"Created default admin user '{admin_user}'", level="INFO")

    # 3. Seed default regular user if not exists
    default_user = session.query(User).filter_by(username="user").first()
    if not default_user:
        new_user = User(
            username="user",
            password_hash=hash_password("user123"),
            role="user",
            must_change_password=False
        )
        session.add(new_user)
        log_event("admin", "Created default user 'user'", level="INFO")

    session.commit()
