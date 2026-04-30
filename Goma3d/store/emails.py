from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def _send(subject, template, context, to):
    context.setdefault('store_name', settings.STORE_NAME)
    context.setdefault('store_email', settings.STORE_EMAIL)
    context.setdefault('whatsapp_number', settings.WHATSAPP_NUMBER)
    html_body = render_to_string(template, context)
    text_body = f"{subject}\n\nAbre este email en un cliente que soporte HTML."
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to] if isinstance(to, str) else to,
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=True)


def send_order_confirmation_client(order):
    _send(
        subject=f'✅ Pedido {order.order_number} recibido — {settings.STORE_NAME}',
        template='emails/order_confirmation_client.html',
        context={
            'order': order,
            'bank_name': settings.BANK_NAME,
            'bank_account_name': settings.BANK_ACCOUNT_NAME,
            'bank_rut': settings.BANK_RUT,
            'bank_account_number': settings.BANK_ACCOUNT_NUMBER,
            'bank_account_type': settings.BANK_ACCOUNT_TYPE,
            'bank_email': settings.BANK_EMAIL,
        },
        to=order.email,
    )


def send_order_notification_admin(order):
    _send(
        subject=f'🛒 Nuevo pedido {order.order_number} — ${order.total_amount:,.0f}',
        template='emails/order_admin.html',
        context={'order': order},
        to=settings.STORE_ADMIN_EMAIL,
    )


def send_custom_order_confirmation_client(obj):
    _send(
        subject=f'📐 Solicitud recibida — {settings.STORE_NAME} te contactará pronto',
        template='emails/custom_order_client.html',
        context={'obj': obj},
        to=obj.email,
    )


def send_custom_order_notification_admin(obj):
    _send(
        subject=f'📐 Nueva cotización: {obj.vehicle_make} {obj.vehicle_model} — {obj.full_name}',
        template='emails/custom_order_admin.html',
        context={'obj': obj},
        to=settings.STORE_ADMIN_EMAIL,
    )


# ── CAMBIO DE ESTADO DE ORDEN ─────────────────────────────────────────────────

STATUS_LABELS = {
    'pending_payment': ('⏳ Esperando pago',         'Tu pedido está esperando confirmación de pago.'),
    'paid':            ('✅ Pago confirmado',         'Confirmamos tu pago. Tu pedido entra a fabricación pronto.'),
    'in_production':   ('🔧 En producción',           'Tu pedido está siendo fabricado. ¡Ya casi!'),
    'shipped':         ('🚚 Pedido enviado',          'Tu pedido fue despachado y está en camino.'),
    'delivered':       ('🎉 Pedido entregado',        '¡Tu pedido fue entregado! Gracias por elegir Gflex3D.'),
    'cancelled':       ('❌ Pedido cancelado',        'Tu pedido fue cancelado. Contáctanos si tienes dudas.'),
}

def send_order_status_change(order, tracking_number=''):
    emoji_title, msg = STATUS_LABELS.get(order.status, ('📦 Actualización', 'El estado de tu pedido cambió.'))
    ctx = {
        'order':          order,
        'status_title':   emoji_title,
        'status_msg':     msg,
        'tracking_number': tracking_number,
    }
    _send(
        subject=f'{emoji_title} — Pedido {order.order_number}',
        template='emails/order_status_change.html',
        context=ctx,
        to=order.email,
    )
