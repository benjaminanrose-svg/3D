import json, urllib.parse
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Q

from .models import (Product, Category, ProductVariant, Material,
                     Order, OrderItem, CustomOrderRequest, Coupon)
from .forms import CheckoutForm, CustomOrderForm, CouponForm
from .emails import (send_order_confirmation_client, send_order_notification_admin,
                     send_custom_order_confirmation_client, send_custom_order_notification_admin)
from .shipping import calcular_envio


# ── CART HELPERS ─────────────────────────────────────────────────────

def _get_cart(request):
    return request.session.get('cart', {})

def _save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True

def _cart_summary(request):
    items, total, count = [], Decimal('0'), 0
    for product_id, data in _get_cart(request).items():
        try:
            product = Product.objects.get(pk=product_id)
            variant = None
            if data.get('variant_id'):
                try: variant = ProductVariant.objects.get(pk=data['variant_id'])
                except ProductVariant.DoesNotExist: pass
            unit_price = variant.get_price() if variant else product.base_price
            qty        = data.get('qty', 1)
            subtotal   = unit_price * qty
            total     += subtotal
            count     += qty
            items.append({'product': product, 'variant': variant, 'qty': qty,
                          'notes': data.get('notes', ''), 'unit_price': unit_price,
                          'subtotal': subtotal, 'product_id': product_id})
        except Product.DoesNotExist:
            pass
    return items, total, count


# ── PÁGINAS ──────────────────────────────────────────────────────────────────

def home(request):
    featured = list(Product.objects.filter(status='active', is_featured=True)[:3])
    if len(featured) < 3:
        featured = list(Product.objects.filter(status='active')[:3])
    return render(request, 'home.html', {
        'categories':       Category.objects.all()[:6],
        'featured_products': featured,
    })
