from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from .models import Customer, User


def date_widget():
    return forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class StyledFormMixin:
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "check"
            else:
                w.attrs["class"] = (w.attrs.get("class", "") + " input").strip()


class StyledForm(StyledFormMixin, forms.Form):
    pass


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["username"].label = "Email"

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class _PasswordPair(StyledForm):
    email = forms.EmailField()
    name = forms.CharField(max_length=150, label="Full name")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput,
                                help_text=password_validation.password_validators_help_text_html())
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return data


class SignupForm(_PasswordPair):
    company = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=30, required=False)
    field_order = ["name", "company", "phone", "email", "password1", "password2"]

    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(d["email"], d["password1"], name=d["name"], role=User.CUSTOMER)
        Customer.objects.create(user=user, name=d["name"], company=d["company"], phone=d["phone"])
        return user


class StaffForm(_PasswordPair):
    def save(self):
        d = self.cleaned_data
        return User.objects.create_user(d["email"], d["password1"], name=d["name"], role=User.STAFF)
