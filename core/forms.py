from django import forms
from .models import ConnectionConfig


class ConnectionForm(forms.ModelForm):
    class Meta:
        model = ConnectionConfig
        fields = ['db_type','host','port','username','password','database_name']
        widgets = {'password': forms.PasswordInput()}
