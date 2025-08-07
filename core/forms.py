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