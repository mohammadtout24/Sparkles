from .models import Category

def menu_categories(request):
    # Fetch all categories from the database
    categories = Category.objects.all()
    # Return a dictionary that will be merged into the template context
    return {'menu_categories': categories}