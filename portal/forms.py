from accounts.forms import StyledModelForm
from accounts.models import Customer


class ProfileForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = ["name", "company", "phone", "address", "tax_id", "state"]
