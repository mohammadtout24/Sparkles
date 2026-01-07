from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('category/<slug:slug>/', views.category_list, name='category_list'),
    path('cart/', views.cart_view, name='cart_view'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('reviews/', views.reviews_page, name='reviews'),
    path('order-success/', views.order_success, name='order_success'),
]
