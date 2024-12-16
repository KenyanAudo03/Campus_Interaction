from django import forms
from .models import Resource

class ResourceForm(forms.ModelForm):
    uploaded_by = forms.CharField(max_length=255, required=False, label="Your Name (optional)")

    class Meta:
        model = Resource
        fields = ['title', 'description', 'file', 'category', 'uploaded_by']
