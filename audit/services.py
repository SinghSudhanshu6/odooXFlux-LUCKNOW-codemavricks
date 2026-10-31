from .models import AuditLog


def log(user, action, obj=None, changes=""):
    """Write one audit row. `user` may be None for system jobs."""
    AuditLog.objects.create(
        actor=user if (user is not None and getattr(user, "is_authenticated", False)) else None,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=getattr(obj, "pk", None),
        object_repr=str(obj)[:200] if obj is not None else "",
        changes=changes[:2000],
    )
