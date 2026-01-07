from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
import urllib.parse
import traceback
import resend

from .models import Product, Category, Review
from .forms import ReviewForm


def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('home')

    # --- 1. Calculate Product Total ---
    products_total = 0
    items_list = []
    
    products = Product.objects.filter(pk__in=cart.keys())

    # Validate Stock
    for product in products:
        cart_qty = cart.get(str(product.pk), 0)
        if product.quantity < cart_qty:
            messages.error(request, f"Sorry, only {product.quantity} left of '{product.name}'.")
            return redirect('cart_view')

    # Calculate Totals
    for product in products:
        quantity = cart.get(str(product.pk), 0)
        if quantity <= 0: continue
            
        subtotal = product.price * quantity
        products_total += subtotal
        items_list.append(f"- {product.name} (x{quantity}): ${subtotal}")

    items_text = "\n".join(items_list)

    # --- 2. Handle Form Submission ---
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        region = request.POST.get('region', '')

        # Calculate Delivery Fee
        delivery_fee = 0
        region_display = "Unknown"

        if region == 'tripoli':
            delivery_fee = 3
            region_display = "Tripoli & Suburbs"
        elif region == 'north':
            delivery_fee = 4
            region_display = "Rest of North"
        elif region == 'other':
            delivery_fee = 5
            region_display = "Beirut / South / Chouf / Bikaa"

        final_total = products_total + delivery_fee

        # Prepare Email
        subject = f"New Order from {name}!"
        message = f"""
You have received a new order via the website.

CUSTOMER DETAILS
----------------
Name:    {name}
Phone:   {phone}
Region:  {region_display}
City:    {city}
Address: {address}

ORDER SUMMARY
-------------
{items_text}

----------------------------
Subtotal:      ${products_total}
Delivery Fee:  ${delivery_fee}
----------------------------
TOTAL TO PAY:  ${final_total}
""".strip()

        try:
            resend.api_key = settings.RESEND_API_KEY
            to_email = settings.DEFAULT_TO_EMAIL or "rayanmahmoudmasri@gmail.com"
            from_email = settings.FROM_EMAIL or "onboarding@resend.dev"

            resend.Emails.send({
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "text": message,
            })

            # Reduce Stock
            for product in products:
                qty_sold = cart.get(str(product.pk), 0)
                if product.quantity >= qty_sold:
                    product.quantity -= qty_sold
                    product.save()

            request.session['cart'] = {}
            messages.success(request, f"Order placed! Total is ${final_total} (including delivery).")
            return redirect('home')

        except Exception as e:
            print("====== RESEND ERROR ======")
            traceback.print_exc()
            messages.error(request, "Error sending email. Check server logs.")

    # Render page with just the product total (delivery is calculated after they pick region)
    return render(request, 'store/checkout.html', {'total_price': products_total})

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
    product = get_object_or_404(Product, pk=pk)
    cart = request.session.get("cart", {})
    str_pk = str(pk)

    current_qty = cart.get(str_pk, 0)

    # Check if adding 1 more exceeds stock
    if current_qty + 1 > product.quantity:
        messages.error(request, "Sorry, we don't have enough stock!")
        return redirect('product_detail', pk=pk)

    cart[str_pk] = current_qty + 1
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
