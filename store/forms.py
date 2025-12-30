from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['name', 'stars', 'text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
            'stars': forms.Select(choices=[(i, f"{i} Stars") for i in range(5, 0, -1)])
        }