from django.urls import path
from . import views as v

urlpatterns = [
    path("products/", v.product_list, name="product_list"),
    path("products/new/", v.product_create, name="product_create"),
    path("products/<int:pk>/", v.product_detail, name="product_detail"),
    path("products/<int:pk>/edit/", v.product_edit, name="product_edit"),
    path("products/<int:pk>/variants/<int:vid>/delete/", v.variant_delete, name="variant_delete"),
    path("plans/", v.plan_list, name="plan_list"),
    path("plans/new/", v.plan_create, name="plan_create"),
    path("plans/<int:pk>/edit/", v.plan_edit, name="plan_edit"),
    path("templates/", v.template_list, name="template_list"),
    path("templates/new/", v.template_create, name="template_create"),
    path("templates/<int:pk>/", v.template_detail, name="template_detail"),
]
