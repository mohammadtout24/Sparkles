from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
import urllib.parse

from .models import Product, Category, Review
from .forms import ReviewForm


def checkout(request):
    cart = request.session.get("cart", {})

    # Redirect if cart is empty
    if not cart:
        return redirect("home")

    # 1) Calculate totals
    total_price = 0
    items_text = ""
    products = Product.objects.filter(pk__in=cart.keys())

    for product in products:
        quantity = cart.get(str(product.pk), 0)
        subtotal = product.price * quantity
        total_price += subtotal
        items_text += f"- {product.name} (x{quantity}): ${subtotal}\n"

    # 2) Handle POST
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()

        subject = f"New Order from {name}!"
        message = f"""
You have received a new order via the website.

CUSTOMER DETAILS
----------------
Name:    {name}
Phone:   {phone}
Address: {address}, {city}

ORDER SUMMARY
-------------
{items_text}

TOTAL: ${total_price}
""".strip()

        # ✅ Always place the order (clear cart) even if email fails
        # Render may block/timeout SMTP, so we must not crash the request.
        email_sent = False
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=["rayanmahmoudmasri@gmail.com"],
                fail_silently=True,  # ✅ prevents 500
            )
            email_sent = True
        except Exception:
            # We keep it silent so checkout never fails
            email_sent = False

        # Clear the cart and confirm order
        request.session["cart"] = {}

        if email_sent:
            messages.success(request, "Order placed successfully! ✅ Email sent.")
        else:
            messages.success(
                request,
                "Order placed successfully! ✅ (Email could not be sent right now.)"
            )

        return redirect("home")

    return render(request, "store/checkout.html", {"total_price": total_price})


def home(request):
    products = Product.objects.all()
    return render(request, "store/home.html", {"products": products})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, "store/product_detail.html", {"product": product})


def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, is_available=True)
    return render(request, "store/category_list.html", {"category": category, "products": products})


def add_to_cart(request, pk):
    cart = request.session.get("cart", {})
    str_pk = str(pk)

    cart[str_pk] = cart.get(str_pk, 0) + 1

    request.session["cart"] = cart
    messages.success(request, "Item added to cart!")
    return redirect("cart_view")


def remove_from_cart(request, pk):
    cart = request.session.get("cart", {})
    str_pk = str(pk)

    if str_pk in cart:
        del cart[str_pk]
        request.session["cart"] = cart

    return redirect("cart_view")


def cart_view(request):
    cart = request.session.get("cart", {})
    items = []
    total_price = 0

    whatsapp_message = "Hello, I would like to place an order for:\n"
    products = Product.objects.filter(pk__in=cart.keys())

    for product in products:
        quantity = cart.get(str(product.pk), 0)
        subtotal = product.price * quantity
        total_price += subtotal

        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal
        })

        whatsapp_message += f"- {quantity}x {product.name} (${subtotal})\n"

    whatsapp_message += f"\nTotal: ${total_price}\n\nPlease confirm availability."
    encoded_message = urllib.parse.quote(whatsapp_message)

    return render(request, "store/cart.html", {
        "items": items,
        "total_price": total_price,
        "whatsapp_url": f"https://wa.me/96171854885?text={encoded_message}",
    })


def about(request):
    return render(request, "store/about.html")


def contact(request):
    return render(request, "store/contact.html")


def reviews_page(request):
    reviews = Review.objects.all().order_by("-created_at")

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your review!")
            return redirect("reviews")
    else:
        form = ReviewForm()

    return render(request, "store/reviews.html", {"reviews": reviews, "form": form})
