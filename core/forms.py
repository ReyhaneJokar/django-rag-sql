from django import forms
from .models import ConnectionConfig, AudioQuery


class ConnectionForm(forms.ModelForm):
    class Meta:
        model = ConnectionConfig
        fields = ['db_type','host','port','username','password','database_name','custom_prompt']
        widgets = {
            'password': forms.PasswordInput(),
            'custom_prompt': forms.Textarea(attrs={'rows':3, 'placeholder':'Optimize the prompt for this connection.'}),
            }

class AudioQueryForm(forms.ModelForm):
    class Meta:
        model = AudioQuery
        fields = ['audio_file']
        widgets = {
            'audio_file': forms.FileInput(attrs={'accept': 'audio/*'})
        }
        
class CustomPromptForm(forms.Form):
    custom_prompt = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "Enter a custom prompt for this database (saved to the current connection)."
        }),
        label="Custom prompt"
    )