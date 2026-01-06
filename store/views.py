from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
import urllib.parse
import traceback
import resend

from .models import Product, Category, Review
from .forms import ReviewForm


# In store/views.py

def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('home')

    # 1. Calculate Product Totals
    subtotal = 0
    items_summary = []
    products = Product.objects.filter(pk__in=cart.keys())

    # Check stock first (Validation)
    for product in products:
        cart_qty = cart.get(str(product.pk), 0)
        if product.quantity < cart_qty:
            messages.error(request, f"Sorry, only {product.quantity} left of '{product.name}'.")
            return redirect('cart_view')

    for product in products:
        quantity = cart.get(str(product.pk), 0)
        line_total = product.price * quantity
        subtotal += line_total
        
        items_summary.append({
            'name': product.name,
            'qty': quantity,
            'total': line_total
        })

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        
        # 2. Get Delivery Option
        region_code = request.POST.get('delivery_region', 'tripoli')
        
        if region_code == 'north':
            delivery_fee = 4
            region_display = "North (Outside Tripoli)"
        elif region_code == 'other':
            delivery_fee = 5
            region_display = "Beirut / South / Beqaa"
        else: # Default to tripoli
            delivery_fee = 3
            region_display = "Tripoli & Suburbs"

        final_total = subtotal + delivery_fee

        # 3. Prepare Email
        items_text = ""
        for item in items_summary:
            items_text += f"- {item['name']} (x{item['qty']}): ${item['total']}\n"

        subject = f"New Order from {name}!"
        message = f"""
NEW ORDER RECEIVED
------------------
Customer: {name}
Phone:    {phone}
Address:  {address}, {city}
Region:   {region_display}

ITEMS
-----
{items_text}

Subtotal: ${subtotal}
Delivery: ${delivery_fee}
TOTAL:    ${final_total}
""".strip()

        try:
            # Send Email
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.FROM_EMAIL or "onboarding@resend.dev",
                "to": [settings.DEFAULT_TO_EMAIL or "rayanmahmoudmasri@gmail.com"],
                "subject": subject,
                "text": message,
            })

            # Reduce Stock
            for product in products:
                qty_sold = cart.get(str(product.pk), 0)
                if product.quantity >= qty_sold:
                    product.quantity -= qty_sold
                    product.save()

            # Clear Cart
            request.session['cart'] = {}
            
            # 4. Show Invoice (Facture)
            context = {
                'name': name,
                'phone': phone,
                'address': address,
                'city': city,
                'region_display': region_display,
                'items_summary': items_summary,
                'subtotal': subtotal,
                'delivery_fee': delivery_fee,
                'final_total': final_total
            }
            return render(request, 'store/invoice.html', context)

        except Exception as e:
            traceback.print_exc()
            messages.error(request, "Error processing order. Please try again.")

    # Convert Decimal to float for JS
    return render(request, 'store/checkout.html', {'total_price': float(subtotal)})

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
