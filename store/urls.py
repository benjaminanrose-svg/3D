from django.urls import path
from . import views
from . import payment

urlpatterns = [
    path('', views.home, name='home'),
    path('catalogo/', views.catalog, name='catalog'),
    path('catalogo/<slug:category_slug>/', views.catalog, name='catalog_category'),
    path('producto/<slug:slug>/', views.product_detail, name='product_detail'),
    path('pedido-a-medida/', views.custom_order, name='custom_order'),

    # Carrito AJAX
    path('carrito/agregar/',    views.add_to_cart,      name='add_to_cart'),
    path('carrito/eliminar/',   views.remove_from_cart, name='remove_from_cart'),
    path('carrito/actualizar/', views.update_cart,      name='update_cart'),
    path('carrito/datos/',      views.cart_data,        name='cart_data'),
    path('carrito/whatsapp/',   views.whatsapp_order,   name='whatsapp_order'),

    # Envío y cupón
    path('envio/calcular/',  views.calcular_envio_ajax, name='calcular_envio'),
    path('cupon/aplicar/',   views.apply_coupon,        name='apply_coupon'),
    path('cupon/guardar/',   views.save_coupon,         name='save_coupon'),

    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('pedido/<str:order_number>/confirmacion/', views.order_confirmation, name='order_confirmation'),

    # ── MercadoPago ──────────────────────────────────────────────────────────
    path('pago/mp/<str:order_number>/',          payment.mp_create_preference, name='mp_pay'),
    path('pago/webhook/',                         payment.mp_webhook,           name='mp_webhook'),
    path('pago/exito/<str:order_number>/',        payment.mp_success,           name='mp_success'),
    path('pago/fallo/<str:order_number>/',        payment.mp_failure,           name='mp_failure'),
    path('pago/pendiente/<str:order_number>/',    payment.mp_pending,           name='mp_pending'),
]
