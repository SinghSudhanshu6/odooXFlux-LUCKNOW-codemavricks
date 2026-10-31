from django import forms
from accounts.forms import StyledForm, date_widget
from .models import Payment


class PaymentForm(StyledForm):
    method = forms.ChoiceField(choices=Payment.METHODS)
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    date = forms.DateField(widget=date_widget())
    note = forms.CharField(max_length=255, required=False)
