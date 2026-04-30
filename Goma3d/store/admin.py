from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import (Category, Material, Product, ProductImage,
                     ProductVariant, CustomOrderRequest, Cart, CartItem,
                     Order, OrderItem, Coupon)
from .emails import send_order_status_change
from .excel_import import generate_template, import_products


# ── SEÑAL: notificar al cliente cuando cambia el estado de su orden ───────────

@receiver(pre_save, sender=Order)
def notify_on_status_change(sender, instance, **kwargs):
    """Dispara email cuando el admin cambia el estado de un pedido."""
    if not instance.pk:
        return
    try:
        previous = Order.objects.get(pk=instance.pk)
        if previous.status != instance.status:
            tracking = getattr(instance, '_tracking_number', '')
            send_order_status_change(instance, tracking_number=tracking)
    except Order.DoesNotExist:
        pass


# ── CATEGORÍAS ────────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'order', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order',)


# ── MATERIALES ────────────────────────────────────────────────────────────────

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'material_type', 'hardness')


# ── PRODUCTOS ─────────────────────────────────────────────────────────────────

class ProductImageInline(admin.TabularInline):
    model  = ProductImage
    extra  = 1
    fields = ('image', 'alt_text', 'order', 'is_primary')


class ProductVariantInline(admin.TabularInline):
    model  = ProductVariant
    extra  = 1
    fields = ('material', 'color', 'size_label', 'price_modifier', 'stock', 'is_available')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display        = ('thumbnail_preview', 'name', 'category', 'base_price', 'status', 'is_featured', 'sku')
    list_display_links  = ('name',)
    list_filter         = ('status', 'category', 'is_featured')
    search_fields       = ('name', 'sku', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines             = [ProductImageInline, ProductVariantInline]
    list_editable       = ('status', 'is_featured')
    readonly_fields     = ('created_at', 'updated_at', 'sku')
    filter_horizontal   = ('materials',)
    change_list_template = 'admin/product_change_list.html'

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="width:48px;height:48px;object-fit:cover;border-radius:6px;">', obj.thumbnail.url)
        return '—'
    thumbnail_preview.short_description = 'Foto'

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('descargar-plantilla/', self.admin_site.admin_view(self.download_template),
                 name='product_download_template'),
            path('importar-excel/', self.admin_site.admin_view(self.import_excel),
                 name='product_import_excel'),
        ]
        return extra + urls

    def download_template(self, request):
        categories = Category.objects.all()
        materials  = Material.objects.all()
        output = generate_template(categories, materials)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=plantilla_productos_gflex3d.xlsx'
        return response

    def import_excel(self, request):
        if request.method == 'POST' and request.FILES.get('excel_file'):
            f = request.FILES['excel_file']
            if not f.name.endswith(('.xlsx', '.xls')):
                messages.error(request, 'El archivo debe ser .xlsx o .xls')
                return redirect('/admin/store/product/')
            try:
                created, updated, errors = import_products(f)
                if created or updated:
                    messages.success(request,
                        f'Importacion completada: {created} productos nuevos, {updated} actualizados.')
                for err in errors:
                    messages.warning(request, f'{err}')
                if not created and not updated and not errors:
                    messages.warning(request, 'No se encontraron productos para importar.')
            except Exception as e:
                messages.error(request, f'Error al leer el archivo: {str(e)}')
            return redirect('/admin/store/product/')
        return redirect('/admin/store/product/')


# ── PEDIDOS PERSONALIZADOS ────────────────────────────────────────────────────

@admin.register(CustomOrderRequest)
class CustomOrderRequestAdmin(admin.ModelAdmin):
    list_display   = ('full_name', 'vehicle_make', 'vehicle_model', 'phone_link', 'status', 'created_at')
    list_filter    = ('status',)
    search_fields  = ('full_name', 'email', 'vehicle_make', 'vehicle_model')
    list_editable  = ('status',)
    readonly_fields = ('created_at', 'updated_at')

    def phone_link(self, obj):
        return format_html('<a href="https://wa.me/{}" target="_blank">💬 {}</a>',
                           obj.phone.replace('+','').replace(' ','').replace('-',''), obj.phone)
    phone_link.short_description = 'Teléfono'


# ── ÓRDENES ───────────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model          = OrderItem
    extra          = 0
    readonly_fields = ('product_name', 'product_sku', 'unit_price', 'get_subtotal')
    fields         = ('product_name', 'product_sku', 'quantity', 'unit_price', 'get_subtotal')


class TrackingFilter(admin.SimpleListFilter):
    title        = 'Estado de pago'
    parameter_name = 'pago'

    def lookups(self, request, model_admin):
        return [('pendiente', 'Esperando pago'), ('pagado', 'Pagados')]

    def queryset(self, request, queryset):
        if self.value() == 'pendiente':
            return queryset.filter(status='pending_payment')
        if self.value() == 'pagado':
            return queryset.filter(status='paid')
        return queryset


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('order_number', 'full_name', 'phone_wa', 'total_colored',
                       'status', 'status_badge', 'payment_method', 'shipping_cost', 'created_at')
    list_filter     = ('status', 'payment_method', TrackingFilter)
    search_fields   = ('order_number', 'full_name', 'email', 'phone')
    readonly_fields = ('order_number', 'created_at', 'updated_at')
    inlines         = [OrderItemInline]
    list_editable   = ('status',)
    ordering        = ('-created_at',)
    save_on_top     = True

    fieldsets = (
        ('📋 Datos del cliente', {
            'fields': ('full_name', 'email', 'phone', 'address', 'city', 'region', 'postal_code')
        }),
        ('💳 Pago y estado', {
            'fields': ('order_number', 'status', 'payment_method', 'payment_status',
                       'payment_id', 'total_amount', 'shipping_cost', 'notification_method')
        }),
        ('📝 Notas', {
            'fields': ('notes',), 'classes': ('collapse',)
        }),
        ('🕐 Fechas', {
            'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('panel/', self.admin_site.admin_view(self.panel_view), name='order_panel'),
            path('notificar/<int:order_id>/', self.admin_site.admin_view(self.notificar_view), name='order_notify'),
        ]
        return extra + urls

    def panel_view(self, request):
        """Panel visual de pedidos pendientes y recientes."""
        pendientes   = Order.objects.filter(status='pending_payment').order_by('-created_at')
        en_produccion = Order.objects.filter(status='in_production').order_by('-created_at')
        enviados     = Order.objects.filter(status='shipped').order_by('-created_at')[:10]
        recientes    = Order.objects.exclude(
            status__in=['pending_payment','in_production','shipped']
        ).order_by('-created_at')[:10]

        ctx = {
            **self.admin_site.each_context(request),
            'title':         'Panel de pedidos',
            'pendientes':    pendientes,
            'en_produccion': en_produccion,
            'enviados':      enviados,
            'recientes':     recientes,
        }
        return render(request, 'admin/order_panel.html', ctx)

    def notificar_view(self, request, order_id):
        """Enviar notificación manual de cambio de estado."""
        order = Order.objects.get(pk=order_id)
        tracking = request.POST.get('tracking', '')
        send_order_status_change(order, tracking_number=tracking)
        messages.success(request, f'Notificación enviada a {order.email}')
        return redirect(f'/admin/store/order/{order_id}/change/')

    def phone_wa(self, obj):
        num = obj.phone.replace('+','').replace(' ','').replace('-','')
        return format_html('<a href="https://wa.me/{}" target="_blank">💬 {}</a>', num, obj.phone)
    phone_wa.short_description = 'Teléfono'

    def total_colored(self, obj):
        amount = f'{int(obj.total_amount):,}'
        return format_html('<strong style="color:#ff5c00;">${}</strong>', amount)
    total_colored.short_description = 'Total'
    total_colored.admin_order_field = 'total_amount'
    
    def status_badge(self, obj):
        colors = {
            'pending_payment': '#f59e0b',
            'paid':            '#10b981',
            'in_production':   '#6366f1',
            'shipped':         '#3b82f6',
            'delivered':       '#10b981',
            'cancelled':       '#ef4444',
        }
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'


# ── CUPONES ───────────────────────────────────────────────────────────────────

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display   = ('code', 'discount_type', 'discount_value', 'uses_display',
                      'min_order_amount', 'active', 'valid_until')
    list_filter    = ('active', 'discount_type')
    search_fields  = ('code',)
    list_editable  = ('active',)
    readonly_fields = ('uses', 'created_at')

    def uses_display(self, obj):
        if obj.max_uses > 0:
            return f'{obj.uses} / {obj.max_uses}'
        return f'{obj.uses} / ∞'
    uses_display.short_description = 'Usos'
