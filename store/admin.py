from django.contrib import admin
from .models import Category, Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'is_available']
    list_editable = ['price', 'is_available']

admin.site.register(Category)
from .models import Review
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['name', 'stars', 'created_at']
    list_filter = ['stars', 'created_at']
    search_fields = ['name', 'text']