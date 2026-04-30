from store.models import Product, ProductVariant
from decimal import Decimal


def get_cart_data(request):
    cart = request.session.get('cart', {})
    items = []
    total = Decimal('0')
    count = 0
    for product_id, item_data in cart.items():
        try:
            product = Product.objects.get(pk=product_id)
            variant = None
            if item_data.get('variant_id'):
                try:
                    variant = ProductVariant.objects.get(pk=item_data['variant_id'])
                except ProductVariant.DoesNotExist:
                    pass
            unit_price = variant.get_price() if variant else product.base_price
            qty = item_data.get('qty', 1)
            subtotal = unit_price * qty
            total += subtotal
            count += qty
            items.append({
                'product': product,
                'variant': variant,
                'qty': qty,
                'notes': item_data.get('notes', ''),
                'unit_price': unit_price,
                'subtotal': subtotal,
                'product_id': product_id,
            })
        except Product.DoesNotExist:
            pass
    return items, total, count


def cart_context(request):
    items, total, count = get_cart_data(request)
    return {
        'cart_items': items,
        'cart_total': total,
        'cart_count': count,
    }
