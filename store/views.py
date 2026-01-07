from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string  # Required for PDF
import urllib.parse
import traceback
import resend
import random
import weasyprint  # Required for PDF generation

from .models import Product, Category, Review
from .forms import ReviewForm


def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('home')

    # --- 1. Prepare Data (Common for GET and POST) ---
    products_total = 0
    items_summary = []  # List for the Invoice HTML
    items_text = ""     # String for the Email Body
    
    products = Product.objects.filter(pk__in=cart.keys())

    # Validate Stock
    for product in products:
        cart_qty = cart.get(str(product.pk), 0)
        if product.quantity < cart_qty:
            messages.error(request, f"Sorry, only {product.quantity} left of '{product.name}'. Please update your cart.")
            return redirect('cart_view')

    # Calculate Totals
    for product in products:
        quantity = cart.get(str(product.pk), 0)
        if quantity <= 0:
            continue
            
        subtotal = product.price * quantity
        products_total += subtotal
        
        # Add to list for Invoice Context
        items_summary.append({
            'name': product.name,
            'qty': quantity,
            'total': float(subtotal)  # ensure it's a number for templates
        })
        
        # Add to string for plain text Email
        items_text += f"- {product.name} (x{quantity}): ${subtotal}\n"

    # --- 2. Handle Form Submission (POST) ---
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        region = request.POST.get('region', '')

        # Calculate Delivery Fees
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
        order_id = f"RS-{random.randint(10000, 99999)}"  # Generate Order ID

        # --- 3. Generate PDF Invoice ---
        # Create context specifically for the PDF template
        invoice_context = {
            'order_id': order_id,
            'name': name,
            'phone': phone,
            'address': address,
            'city': city,
            'region_display': region_display,
            'items_summary': items_summary,
            'subtotal': float(products_total),
            'delivery_fee': float(delivery_fee),
            'final_total': float(final_total),
        }

        # Render the HTML to a string
        html_invoice = render_to_string('store/invoice.html', invoice_context, request=request)

        # Create PDF bytes (base_url is needed to find images/css)
        pdf_file = weasyprint.HTML(string=html_invoice, base_url=request.build_absolute_uri()).write_pdf()

        # --- 4. Prepare Email Content ---
        subject = f"Order Confirmation: {order_id}"
        message = f"""
Hello {name},

Thank you for your order! 
Your Order ID is: {order_id}

We have attached your invoice to this email.

ORDER SUMMARY
-------------
{items_text}

Subtotal:     ${products_total}
Delivery Fee: ${delivery_fee} ({region_display})
TOTAL:        ${final_total}

We will contact you shortly at {phone} for delivery.

Best regards,
Rayan Sparkles Team
""".strip()

        try:
            # Send Email with Attachment
            resend.api_key = settings.RESEND_API_KEY
            
            resend.Emails.send({
                "from": settings.FROM_EMAIL,
                "to": [settings.DEFAULT_TO_EMAIL],  # In prod, change to [to_email] to send to customer
                "subject": subject,
                "text": message,
                "attachments": [
                    {
                        "filename": f"Invoice_{order_id}.pdf",
                        "content": list(pdf_file)  # Resend requires a list of integers (bytes)
                    }
                ]
            })

            # Reduce Stock
            for product in products:
                qty_sold = cart.get(str(product.pk), 0)
                if product.quantity >= qty_sold:
                    product.quantity -= qty_sold
                    product.save()

            # --- SAVE DATA FOR SUCCESS PAGE ---
            # We save the exact same context to session so we can show it on the next page
            request.session['invoice_data'] = invoice_context

            # Clear Cart
            request.session['cart'] = {}
            
            # Redirect to Success Page
            return redirect('order_success')

        except Exception as e:
            print("====== RESEND ERROR ======")
            print("Exception:", repr(e))
            traceback.print_exc()
            print("==========================")
            messages.error(request, "Order processed, but email failed to send. Please contact support.")
            # Even if email fails, we might still want to show success if stock was reduced
            # For now, let's redirect back to home or handle gracefully
            return redirect('home')

    # If GET request, render the checkout form
    return render(request, 'store/checkout.html', {'total_price': products_total})


def order_success(request):
    """
    Displays the invoice immediately after a successful purchase.
    Reads data from the session.
    """
    # Retrieve the data we saved in the session
    invoice_data = request.session.get('invoice_data')
    
    # Security: If no data exists (user tried to access url directly), send them home
    if not invoice_data:
        return redirect('home')

    return render(request, 'store/invoice.html', invoice_data)


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
