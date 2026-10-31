from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views
from .forms import LoginForm

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(authentication_form=LoginForm, redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        email_template_name="registration/password_reset_email.txt",
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password-reset/confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("password-reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("admin-panel/staff/", views.staff_list, name="staff_list"),
    path("admin-panel/staff/new/", views.staff_create, name="staff_create"),
]
