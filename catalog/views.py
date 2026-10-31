from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.mixins import ADMIN, ALL, STAFF, role_required
from accounts.utils import model_form_view, paginate
from .forms import PlanForm, ProductForm, TemplateForm, TemplateLineForm, VariantForm
from .models import Plan, Product, QuotationTemplate


@role_required(*STAFF)
def product_list(request):
    q = request.GET.get("q", "").strip()
    qs = Product.objects.annotate(nvar=Count("variants")).order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "catalog/product_list.html", {"page": paginate(request, qs), "q": q})


@role_required(*ADMIN)
def product_create(request):
    return model_form_view(request, ProductForm, title="New product", back="product_list")


@role_required(*ADMIN)
def product_edit(request, pk):
    p = get_object_or_404(Product, pk=pk)
    return model_form_view(request, ProductForm, instance=p, title=f"Edit {p.name}", back="product_list")


@role_required(*STAFF)
def product_detail(request, pk):
    p = get_object_or_404(Product, pk=pk)
    form = VariantForm(request.POST or None)
    if request.method == "POST":
        if request.user.role != "admin":
            return redirect("product_detail", pk=pk)
        if form.is_valid():
            v = form.save(commit=False)
            v.product = p
            v.save()
            messages.success(request, "Variant added.")
            return redirect("product_detail", pk=pk)
    return render(request, "catalog/product_detail.html", {"product": p, "form": form})


@role_required(*ADMIN)
@require_POST
def variant_delete(request, pk, vid):
    get_object_or_404(Product, pk=pk).variants.filter(pk=vid).delete()
    return redirect("product_detail", pk=pk)


@role_required(*ALL)
def plan_list(request):
    return render(request, "catalog/plan_list.html", {"plans": Plan.objects.all()})


@role_required(*ADMIN)
def plan_create(request):
    return model_form_view(request, PlanForm, title="New plan", back="plan_list")


@role_required(*ADMIN)
def plan_edit(request, pk):
    p = get_object_or_404(Plan, pk=pk)
    return model_form_view(request, PlanForm, instance=p, title=f"Edit {p.name}", back="plan_list")


@role_required(*STAFF)
def template_list(request):
    return render(request, "catalog/template_list.html", {"templates": QuotationTemplate.objects.select_related("plan")})


@role_required(*ADMIN)
def template_create(request):
    return model_form_view(request, TemplateForm, title="New quotation template", back="template_list")


@role_required(*STAFF)
def template_detail(request, pk):
    t = get_object_or_404(QuotationTemplate.objects.select_related("plan"), pk=pk)
    form = TemplateLineForm(request.POST or None)
    if request.method == "POST" and request.user.role == "admin" and form.is_valid():
        ln = form.save(commit=False)
        ln.template = t
        ln.save()
        messages.success(request, "Line added.")
        return redirect("template_detail", pk=pk)
    return render(request, "catalog/template_detail.html",
                  {"t": t, "lines": t.lines.select_related("product", "variant"), "form": form})
