from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
import urllib.parse
import traceback
import resend
import random
from .models import Product, Category, Review
from .forms import ReviewForm


def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('home')

    # --- 1. Prepare Data ---
    products_total = 0
    items_summary = [] # List for the Invoice HTML
    items_text = ""    # String for the Email
    
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
        
        # Add to list for Invoice
        items_summary.append({
            'name': product.name,
            'qty': quantity,
            'total': float(subtotal) # ensure it's a number
        })
        
        # Add to string for Email
        items_text += f"- {product.name} (x{quantity}): ${subtotal}\n"

    # --- 2. Handle Form Submission ---
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        region = request.POST.get('region', '')

        # Calculate Fees
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
        order_id = f"RS-{random.randint(10000, 99999)}" # Generate Order ID

        # Prepare Email
        subject = f"New Order {order_id} from {name}"
        message = f"""
New Order Received!
Order ID: {order_id}

CUSTOMER
--------
Name:    {name}
Phone:   {phone}
Region:  {region_display}
City:    {city}
Address: {address}

ITEMS
-----
{items_text}

SUMMARY
-------
Subtotal:     ${products_total}
Delivery:     ${delivery_fee}
TOTAL:        ${final_total}
""".strip()

        try:
            # Send Email
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.FROM_EMAIL,
                "to": [settings.DEFAULT_TO_EMAIL],
                "subject": subject,
                "text": message,
            })

            # Reduce Stock
            for product in products:
                qty_sold = cart.get(str(product.pk), 0)
                if product.quantity >= qty_sold:
                    product.quantity -= qty_sold
                    product.save()

            # --- SAVE DATA FOR INVOICE PAGE ---
            request.session['invoice_data'] = {
                'order_id': order_id,
                'name': name,
                'phone': phone,
                'address': address,
                'city': city,
                'region_display': region_display,
                'items_summary': items_summary,
                'subtotal': float(products_total),
                'delivery_fee': delivery_fee,
                'final_total': float(final_total),
            }

            # Clear Cart
            request.session['cart'] = {}
            
            # Redirect to Success Page
            return redirect('order_success')

        except Exception as e:
            print("Email Error:", e)
            messages.error(request, "Order processed but email failed.")
            return redirect('home')

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
