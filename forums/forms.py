from django import forms
from .models import Forum, Post
from django.core.exceptions import ValidationError

class ForumForm(forms.ModelForm):
    class Meta:
        model = Forum
        fields = ["name", "description", "display_picture"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control name__input",
                    "placeholder": "Enter forum name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control description__input",
                    "id": "description__input",
                    "rows": 4,
                    "cols": 40,
                    "placeholder": "Enter a description",
                    "maxlength": "250",  # Set the maximum number of characters
                }
            ),
            "display_picture": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_picture"].required = False

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image', 'video']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control', 
                'placeholder': 'Write something interesting...',
                'rows': 4,
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'video': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'video/*'
            }),
        }

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if video:
            max_size_mb = 10
            if video.size > max_size_mb * 1024 * 1024:
                raise ValidationError(f"Video file size must not exceed {max_size_mb}MB.")
        return video
