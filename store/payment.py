"""
Integración MercadoPago para Gflex3D.

Flujo completo:
  1. checkout() → crea la Order con status='pending_payment'
  2. mp_create_preference() → crea preferencia en MP y redirige al cliente
  3. Cliente paga en MP → MP llama a mp_webhook() con la notificación
  4. mp_webhook() verifica la firma, actualiza el estado de la Order
  5. MP redirige al cliente a mp_success / mp_failure / mp_pending

Claves en .env:
  MP_ACCESS_TOKEN=TEST-xxx    (pruebas) o APP_USR-xxx (producción)
  MP_WEBHOOK_SECRET=xxx       (firma del webhook, se genera en el panel MP)
  SITE_DOMAIN=https://gflex3d.cl
"""

import hashlib, hmac, json, logging
import mercadopago
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Order
from .emails import send_order_confirmation_client, send_order_status_change

logger = logging.getLogger(__name__)


def _sdk():
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


# ── 1. CREAR PREFERENCIA ─────────────────────────────────────────────────────

def mp_create_preference(request, order_number):
    """
    Crea la preferencia de pago en MercadoPago y redirige al cliente.
    Se llama justo después de confirmar el pedido cuando el método es 'mercadopago'.
    """
    order = get_object_or_404(Order, order_number=order_number)

    if not settings.MP_ACCESS_TOKEN:
        # Sin clave configurada → mostrar página de instrucciones
        return render(request, 'payment/mp_not_configured.html', {'order': order})

    domain = settings.SITE_DOMAIN.rstrip('/')

    # Construir ítems de la preferencia
    items = []
    for item in order.items.all():
        items.append({
            'id':          item.product_sku,
            'title':       item.product_name[:256],
            'quantity':    item.quantity,
            'unit_price':  float(item.unit_price),
            'currency_id': 'CLP',
        })

    # Si hay costo de envío, agregarlo como ítem
    if order.shipping_cost and order.shipping_cost > 0:
        items.append({
            'id':         'ENVIO',
            'title':      'Costo de envío',
            'quantity':   1,
            'unit_price': float(order.shipping_cost),
            'currency_id': 'CLP',
        })

    preference_data = {
        'items': items,
        'payer': {
            'name':  order.full_name.split()[0],
            'surname': ' '.join(order.full_name.split()[1:]) or '',
            'email': order.email,
            'phone': {'number': order.phone},
        },
        'back_urls': {
            'success': f'{domain}/pago/exito/{order.order_number}/',
            'failure': f'{domain}/pago/fallo/{order.order_number}/',
            'pending': f'{domain}/pago/pendiente/{order.order_number}/',
        },
        'auto_return':          'approved',
        'notification_url':     f'{domain}/pago/webhook/',
        'external_reference':   order.order_number,
        'statement_descriptor': 'GFLEX3D',
        'expires':              False,
        'payment_methods': {
            'excluded_payment_types': [],
            'installments':           12,   # hasta 12 cuotas
        },
    }

    try:
        sdk         = _sdk()
        result      = sdk.preference().create(preference_data)
        preference  = result['response']

        if result['status'] == 201:
            order.payment_id = preference['id']
            order.save(update_fields=['payment_id'])
            # En producción usar 'init_point', en sandbox 'sandbox_init_point'
            is_test   = settings.MP_ACCESS_TOKEN.startswith('TEST')
            init_url  = preference.get('sandbox_init_point' if is_test else 'init_point', '')
            logger.info(f'MP preference created: {preference["id"]} for order {order.order_number}')
            return redirect(init_url)
        else:
            logger.error(f'MP preference error: {result}')
            return render(request, 'payment/mp_error.html', {
                'order': order, 'error': 'No se pudo crear la preferencia de pago.'
            })
    except Exception as e:
        logger.exception(f'MP create_preference exception: {e}')
        return render(request, 'payment/mp_error.html', {
            'order': order, 'error': str(e)
        })


# ── 2. WEBHOOK ────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def mp_webhook(request):
    """
    Recibe notificaciones de pago de MercadoPago.
    MercadoPago hace POST a esta URL cuando cambia el estado de un pago.
    """
    # Verificar firma HMAC (si está configurada)
    secret = settings.MP_WEBHOOK_SECRET
    if secret:
        sig_header = request.headers.get('x-signature', '')
        ts_header  = request.headers.get('x-request-id', '')
        if not _verify_mp_signature(request.body, sig_header, ts_header, secret):
            logger.warning('MP webhook: firma inválida')
            return HttpResponse(status=400)

    try:
        data   = json.loads(request.body)
        topic  = data.get('type') or request.GET.get('topic', '')
        obj_id = data.get('data', {}).get('id') or request.GET.get('id', '')

        logger.info(f'MP webhook: type={topic} id={obj_id}')

        if topic == 'payment' and obj_id:
            _process_payment(obj_id)

    except Exception as e:
        logger.exception(f'MP webhook exception: {e}')
        return HttpResponse(status=500)

    return HttpResponse(status=200)


def _verify_mp_signature(body: bytes, sig_header: str, request_id: str, secret: str) -> bool:
    """Verifica la firma HMAC-SHA256 de MercadoPago."""
    try:
        parts  = dict(p.split('=', 1) for p in sig_header.split(',') if '=' in p)
        ts     = parts.get('ts', '')
        v1     = parts.get('v1', '')
        msg    = f'id:{request_id};request-date:{ts};'
        digest = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, v1)
    except Exception:
        return False


def _process_payment(payment_id: str):
    """Consulta el estado del pago en MP y actualiza la Order."""
    try:
        sdk     = _sdk()
        result  = sdk.payment().get(payment_id)
        payment = result['response']

        status     = payment.get('status', '')
        ext_ref    = payment.get('external_reference', '')
        mp_amount  = payment.get('transaction_amount', 0)

        logger.info(f'MP payment {payment_id}: status={status} ref={ext_ref}')

        if not ext_ref:
            return

        try:
            order = Order.objects.get(order_number=ext_ref)
        except Order.DoesNotExist:
            logger.warning(f'MP webhook: order {ext_ref} not found')
            return

        # Mapeo de estados MP → estados de la Order
        STATUS_MAP = {
            'approved':    'paid',
            'pending':     'pending_payment',
            'in_process':  'pending_payment',
            'rejected':    'cancelled',
            'cancelled':   'cancelled',
            'refunded':    'cancelled',
            'charged_back': 'cancelled',
        }

        new_status = STATUS_MAP.get(status)
        if new_status and order.status != new_status:
            order.status         = new_status
            order.payment_status = status
            order.payment_id     = str(payment_id)
            order.save(update_fields=['status', 'payment_status', 'payment_id'])
            logger.info(f'Order {ext_ref} → {new_status}')
            # Notificar al cliente del cambio de estado
            send_order_status_change(order)

    except Exception as e:
        logger.exception(f'_process_payment error: {e}')


# ── 3. PÁGINAS DE RETORNO ─────────────────────────────────────────────────────

def mp_success(request, order_number):
    """MP redirige aquí cuando el pago fue aprobado."""
    order = get_object_or_404(Order, order_number=order_number)

    # MP pasa payment_id en query params; procesamos si aún no fue procesado
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')
    if payment_id and order.status == 'pending_payment':
        _process_payment(payment_id)
        order.refresh_from_db()

    return render(request, 'payment/mp_success.html', {
        'order':             order,
        'whatsapp_number':   settings.WHATSAPP_NUMBER,
        'bank_name':         settings.BANK_NAME,
        'bank_account_name': settings.BANK_ACCOUNT_NAME,
        'bank_account_number': settings.BANK_ACCOUNT_NUMBER,
        'bank_account_type': settings.BANK_ACCOUNT_TYPE,
        'bank_rut':          settings.BANK_RUT,
        'bank_email':        settings.BANK_EMAIL,
    })


def mp_failure(request, order_number):
    """MP redirige aquí cuando el pago fue rechazado."""
    order  = get_object_or_404(Order, order_number=order_number)
    reason = request.GET.get('collection_status', 'rejected')
    return render(request, 'payment/mp_failure.html', {
        'order': order, 'reason': reason
    })


def mp_pending(request, order_number):
    """MP redirige aquí cuando el pago queda pendiente (ej. efectivo)."""
    order = get_object_or_404(Order, order_number=order_number)
    return render(request, 'payment/mp_pending.html', {'order': order})
