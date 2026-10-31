from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ADMIN = ("admin",)
STAFF = ("admin", "staff")
ALL = ("admin", "staff", "customer")


def role_required(*roles):
    def deco(view):
        @wraps(view)
        def inner(request, *a, **kw):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *a, **kw)
        return login_required(inner)
    return deco


def scope_customer(user, qs):
    """Customers only ever see their own rows (prevents IDOR)."""
    if user.role == "customer":
        cust = getattr(user, "customer", None)
        return qs.filter(customer=cust) if cust else qs.none()
    return qs
