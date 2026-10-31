from django.shortcuts import render

from accounts.mixins import ADMIN, role_required
from accounts.utils import paginate
from .models import AuditLog


@role_required(*ADMIN)
def audit_list(request):
    qs = AuditLog.objects.select_related("actor")
    q, typ = request.GET.get("q", "").strip(), request.GET.get("type", "")
    if q:
        qs = qs.filter(object_repr__icontains=q) | qs.filter(actor__email__icontains=q) | qs.filter(action__icontains=q)
    if typ:
        qs = qs.filter(object_type=typ)
    types = AuditLog.objects.exclude(object_type="").values_list("object_type", flat=True).distinct().order_by("object_type")
    return render(request, "audit/list.html", {"page": paginate(request, qs, 40), "q": q, "typ": typ, "types": types})
