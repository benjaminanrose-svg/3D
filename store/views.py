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


# ── CART HELPERS ─────────────────────────────────────────────────────────────

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


# ── PÁGINAS ───────────────────────────────────────────────────────────────────

def home(request):
    featured = Product.objects.filter(status='active', is_featured=True)[:3]
    if featured.count() < 3:
        featured = Product.objects.filter(status='active')[:3]
    return render(request, 'home.html', {
        'categories':       Category.objects.all()[:6],
        'featured_products': featured,
    })


def catalog(request, category_slug=None):
    products         = Product.objects.filter(status='active').select_related('category')
    categories       = Category.objects.all()
    materials        = Material.objects.all()
    current_category = None

    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    # ── Búsqueda inteligente ─────────────────────────────────────────────────
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(sku__icontains=q) |                    # búsqueda por SKU
            Q(compatible_vehicles__icontains=q) |    # por vehículo
            Q(category__name__icontains=q)           # por categoría
        )

    material_id = request.GET.get('material', '')
    if material_id:
        products = products.filter(materials__id=material_id)

    vehiculo = request.GET.get('vehiculo', '').strip()
    if vehiculo:
        products = products.filter(compatible_vehicles__icontains=vehiculo)

    try:
        precio_min = int(request.GET.get('precio_min') or 0)
        precio_max = int(request.GET.get('precio_max') or 0)
    except ValueError:
        precio_min = precio_max = 0
    if precio_min: products = products.filter(base_price__gte=precio_min)
    if precio_max: products = products.filter(base_price__lte=precio_max)

    sort = request.GET.get('sort', 'newest')
    products = products.order_by(
        {'newest': '-created_at', 'price_asc': 'base_price',
         'price_desc': '-base_price', 'name': 'name'}.get(sort, '-created_at')
    ).distinct()

    paginator = Paginator(products, 12)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'catalog.html', {
        'page_obj': page_obj, 'categories': categories, 'materials': materials,
        'current_category': current_category, 'total_count': paginator.count,
        'q': q, 'vehiculo': vehiculo, 'material_id': material_id,
        'precio_min': precio_min or '', 'precio_max': precio_max or '', 'sort': sort,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, status='active')
    return render(request, 'product_detail.html', {
        'product':  product,
        'variants': product.variants.filter(is_available=True),
        'images':   product.images.all(),
        'related':  Product.objects.filter(
                        category=product.category, status='active'
                    ).exclude(pk=product.pk)[:4],
    })


def custom_order(request):
    if request.method == 'POST':
        form = CustomOrderForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            send_custom_order_confirmation_client(obj)
            send_custom_order_notification_admin(obj)
            if request.POST.get('via') == 'whatsapp':
                msg = (f"Hola Gflex3D, quiero solicitar una pieza a medida.\n"
                       f"Nombre: {obj.full_name}\n"
                       f"Vehículo: {obj.vehicle_make} {obj.vehicle_model} {obj.vehicle_year}\n"
                       f"Pieza: {obj.part_description}\nCantidad: {obj.quantity}")
                return redirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={urllib.parse.quote(msg)}")
            messages.success(request, '✅ Solicitud enviada. Te contactaremos en menos de 24 hrs.')
            return redirect('custom_order')
    else:
        form = CustomOrderForm()
    return render(request, 'custom_order.html', {'form': form})


# ── CUPÓN AJAX ────────────────────────────────────────────────────────────────

def apply_coupon(request):
    code     = request.GET.get('code', '').strip().upper()
    subtotal = Decimal(request.GET.get('subtotal', '0'))
    if not code:
        return JsonResponse({'ok': False, 'error': 'Ingresa un código.'})
    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cupón no encontrado.'})
    valid, msg = coupon.is_valid()
    if not valid:
        return JsonResponse({'ok': False, 'error': msg})
    if coupon.min_order_amount > 0 and subtotal < coupon.min_order_amount:
        return JsonResponse({'ok': False,
            'error': f'Monto mínimo para este cupón: ${coupon.min_order_amount:,.0f}'})
    discount = coupon.calc_discount(subtotal)
    return JsonResponse({
        'ok':       True,
        'code':     coupon.code,
        'discount': int(discount),
        'label':    str(coupon),
    })


# ── ENVÍO AJAX ────────────────────────────────────────────────────────────────

def calcular_envio_ajax(request):
    region = request.GET.get('region', '').strip()
    if not region:
        return JsonResponse({'ok': False})
    d = calcular_envio(region)
    return JsonResponse({'ok': True, 'costo': int(d['costo']),
                         'dias': d['dias'], 'carrier': d['carrier']})


# ── CARRITO AJAX ──────────────────────────────────────────────────────────────

@require_POST
def add_to_cart(request):
    data       = json.loads(request.body)
    product_id = str(data.get('product_id'))
    qty        = int(data.get('qty', 1))
    try: Product.objects.get(pk=product_id)
    except (Product.DoesNotExist, Exception):
        return JsonResponse({'ok': False}, status=404)
    cart = _get_cart(request)
    if product_id in cart: cart[product_id]['qty'] += qty
    else: cart[product_id] = {'qty': qty, 'variant_id': data.get('variant_id'),
                               'notes': data.get('notes', '')}
    _save_cart(request, cart)
    _, total, count = _cart_summary(request)
    return JsonResponse({'ok': True, 'cart_count': count, 'cart_total': str(total)})

@require_POST
def remove_from_cart(request):
    data = json.loads(request.body)
    cart = _get_cart(request)
    cart.pop(str(data.get('product_id')), None)
    _save_cart(request, cart)
    _, total, count = _cart_summary(request)
    return JsonResponse({'ok': True, 'cart_count': count, 'cart_total': str(total)})

@require_POST
def update_cart(request):
    data       = json.loads(request.body)
    product_id = str(data.get('product_id'))
    qty        = int(data.get('qty', 1))
    cart       = _get_cart(request)
    if product_id in cart:
        if qty <= 0: del cart[product_id]
        else: cart[product_id]['qty'] = qty
    _save_cart(request, cart)
    _, total, count = _cart_summary(request)
    return JsonResponse({'ok': True, 'cart_count': count, 'cart_total': str(total)})

def cart_data(request):
    items, total, count = _cart_summary(request)
    return JsonResponse({'count': count, 'total': str(total),
        'items': [{'product_id': str(i['product'].pk), 'name': i['product'].name,
                   'qty': i['qty'], 'unit_price': str(i['unit_price']),
                   'subtotal': str(i['subtotal']),
                   'variant': str(i['variant']) if i['variant'] else ''} for i in items]})

def whatsapp_order(request):
    items, total, _ = _cart_summary(request)
    if not items: return redirect('home')
    lines = ['🛒 *Pedido Gflex3D*\n']
    for i in items:
        lines.append(f"• {i['product'].name} x{i['qty']} — ${i['subtotal']:,.0f}")
    lines.append(f"\n*Total: ${total:,.0f}*\nQuiero confirmar este pedido.")
    return redirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={urllib.parse.quote(chr(10).join(lines))}")


# ── CHECKOUT ──────────────────────────────────────────────────────────────────

def checkout(request):
    items, subtotal, count = _cart_summary(request)
    if not items:
        return redirect('catalog')

    sd       = calcular_envio('Metropolitana de Santiago')
    shipping = sd['costo']

    # Recuperar cupón de la sesión
    coupon_code     = request.session.get('coupon_code', '')
    coupon_discount = Decimal(str(request.session.get('coupon_discount', '0')))
    coupon_obj      = None
    if coupon_code:
        try:
            coupon_obj = Coupon.objects.get(code=coupon_code)
            valid, _ = coupon_obj.is_valid()
            if not valid:
                coupon_code = ''
                coupon_discount = Decimal('0')
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)
        except Coupon.DoesNotExist:
            coupon_code = ''
            coupon_discount = Decimal('0')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            d        = form.cleaned_data
            sd       = calcular_envio(d['region'])
            shipping = sd['costo']
            grand_total = subtotal - coupon_discount + shipping

            order = Order(
                full_name=d['full_name'], email=d['email'], phone=d['phone'],
                address=d['address'], city=d['city'], region=d['region'],
                postal_code=d.get('postal_code', ''),
                payment_method=d['payment_method'],
                notification_method=d['notification_method'],
                notes=d.get('notes', ''),
                total_amount=grand_total, shipping_cost=shipping,
                status='pending_payment',
            )
            order.save()

            for item in items:
                OrderItem.objects.create(
                    order=order, product=item['product'], variant=item['variant'],
                    product_name=item['product'].name, product_sku=item['product'].sku,
                    quantity=item['qty'], unit_price=item['unit_price'],
                    custom_notes=item['notes'],
                )

            # Registrar uso del cupón
            if coupon_obj:
                coupon_obj.uses += 1
                coupon_obj.save(update_fields=['uses'])
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)

            send_order_confirmation_client(order)
            send_order_notification_admin(order)

            if d['notification_method'] in ('whatsapp', 'both'):
                wa_msg = (f"Hola {d['full_name']}, recibimos tu pedido *{order.order_number}* "
                          f"por ${grand_total:,.0f} CLP. "
                          f"{'Esperamos tu transferencia.' if d['payment_method'] == 'bank_transfer' else 'Procesando pago.'} "
                          f"¡Gracias por elegir Gflex3D! 🚗")
                request.session['wa_confirm_url'] = (
                    f"https://wa.me/{d['phone'].replace('+','').replace(' ','').replace('-','')}"
                    f"?text={urllib.parse.quote(wa_msg)}")

            _save_cart(request, {})

            # Redirigir según método de pago
            if d['payment_method'] == 'mercadopago' and settings.MP_ACCESS_TOKEN:
                return redirect('mp_pay', order_number=order.order_number)
            return redirect('order_confirmation', order_number=order.order_number)
    else:
        form = CheckoutForm()

    grand_total = subtotal - coupon_discount + shipping

    return render(request, 'checkout.html', {
        'form': form, 'cart_items': items,
        'cart_subtotal':    subtotal,
        'shipping':         shipping,
        'shipping_dias':    sd['dias'],
        'shipping_carrier': sd['carrier'],
        'coupon_code':      coupon_code,
        'coupon_discount':  coupon_discount,
        'grand_total':      grand_total,
    })


def save_coupon(request):
    """Guardar cupón validado en la sesión."""
    code     = request.GET.get('code', '').strip().upper()
    subtotal = Decimal(request.GET.get('subtotal', '0'))
    if not code:
        request.session.pop('coupon_code', None)
        request.session.pop('coupon_discount', None)
        return JsonResponse({'ok': True, 'removed': True})
    try:
        coupon = Coupon.objects.get(code=code)
        valid, msg = coupon.is_valid()
        if not valid:
            return JsonResponse({'ok': False, 'error': msg})
        if coupon.min_order_amount > 0 and subtotal < coupon.min_order_amount:
            return JsonResponse({'ok': False,
                'error': f'Monto mínimo: ${coupon.min_order_amount:,.0f}'})
        discount = coupon.calc_discount(subtotal)
        request.session['coupon_code']     = coupon.code
        request.session['coupon_discount'] = str(discount)
        return JsonResponse({'ok': True, 'code': coupon.code,
                             'discount': int(discount), 'label': str(coupon)})
    except Coupon.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cupón no encontrado.'})


def order_confirmation(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    wa_confirm_url = request.session.pop('wa_confirm_url', None)
    return render(request, 'order_confirmation.html', {
        'order': order,
        'bank_name':           settings.BANK_NAME,
        'bank_account_name':   settings.BANK_ACCOUNT_NAME,
        'bank_account_number': settings.BANK_ACCOUNT_NUMBER,
        'bank_account_type':   settings.BANK_ACCOUNT_TYPE,
        'bank_rut':            settings.BANK_RUT,
        'bank_email':          settings.BANK_EMAIL,
        'whatsapp_number':     settings.WHATSAPP_NUMBER,
        'wa_confirm_url':      wa_confirm_url,
    })


# ── PÁGINAS DE ERROR ──────────────────────────────────────────────────────────

def error_404(request, exception):
    return render(request, '404.html', status=404)

def error_500(request):
    return render(request, '500.html', status=500)
