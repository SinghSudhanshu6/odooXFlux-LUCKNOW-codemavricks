from django import forms
from accounts.forms import StyledModelForm
from .models import ReminderRule


class ReminderRuleForm(StyledModelForm):
    class Meta:
        model = ReminderRule
        fields = ["name", "offset_days", "subject", "body", "tone", "creates_task", "flags_at_risk", "active"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}
