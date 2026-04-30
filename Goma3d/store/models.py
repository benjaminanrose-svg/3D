from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid


# ─────────────────────────────────────────
# CATEGORÍAS
# ─────────────────────────────────────────
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre")
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Nombre de ícono (ej: 'pipe', 'gear')")
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# MATERIAL
# ─────────────────────────────────────────
class Material(models.Model):
    MATERIAL_CHOICES = [
        ("polyurethane", "Poliuretano"),
        ("rubber", "Caucho"),
        ("polyurethane_rubber", "Poliuretano/Caucho"),
    ]
    name = models.CharField(max_length=100)
    material_type = models.CharField(max_length=30, choices=MATERIAL_CHOICES)
    hardness = models.CharField(max_length=20, blank=True, help_text="Ej: 80 Shore A")
    description = models.TextField(blank=True)
    color_options = models.CharField(max_length=200, blank=True, help_text="Colores disponibles separados por coma")

    def __str__(self):
        return f"{self.name} ({self.get_material_type_display()})"


# ─────────────────────────────────────────
# PRODUCTO
# ─────────────────────────────────────────
class Product(models.Model):
    STATUS_CHOICES = [
        ("active", "Activo"),
        ("inactive", "Inactivo"),
        ("on_request", "Solo a pedido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True, blank=True)
    description = models.TextField(verbose_name="Descripción")
    short_description = models.CharField(max_length=300, blank=True)

    # Materiales y variantes
    materials = models.ManyToManyField(Material, blank=True)
    compatible_vehicles = models.TextField(blank=True, help_text="Marcas/modelos compatibles, uno por línea")

    # Dimensiones
    width_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    depth_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    weight_g = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # Precio
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio base")
    custom_price_note = models.CharField(max_length=200, blank=True, help_text="Nota sobre precio personalizado")

    # 3D Model
    model_3d_file = models.FileField(upload_to="models_3d/", blank=True, null=True,
                                     help_text="Archivo .glb o .gltf para vista 3D")
    model_3d_url = models.URLField(blank=True, help_text="URL externa del modelo 3D")

    # Imágenes
    thumbnail = models.ImageField(upload_to="products/thumbnails/", blank=True, null=True)

    # Estado y metadata
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="active")
    is_featured = models.BooleanField(default=False)
    min_order_qty = models.PositiveIntegerField(default=1, help_text="Cantidad mínima de pedido")
    production_days = models.PositiveIntegerField(default=7, help_text="Días de producción estimados")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            self.sku = f"GFX-{str(self.id)[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_model_3d(self):
        if self.model_3d_file:
            return self.model_3d_file.url
        return self.model_3d_url or None


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]


# ─────────────────────────────────────────
# VARIANTE DE PRODUCTO
# ─────────────────────────────────────────
class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True)
    color = models.CharField(max_length=50, blank=True)
    size_label = models.CharField(max_length=50, blank=True, help_text="Ej: 'M', '25mm', 'Tipo A'")
    price_modifier = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                         help_text="Ajuste de precio (+/-)")
    stock = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)

    def get_price(self):
        return self.product.base_price + self.price_modifier

    def __str__(self):
        return f"{self.product.name} - {self.material} {self.color} {self.size_label}"


# ─────────────────────────────────────────
# PEDIDO PERSONALIZADO
# ─────────────────────────────────────────
class CustomOrderRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("reviewing", "En revisión"),
        ("quoted", "Cotizado"),
        ("approved", "Aprobado"),
        ("in_production", "En producción"),
        ("completed", "Completado"),
        ("rejected", "Rechazado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Datos contacto
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    # Descripción de la pieza
    part_description = models.TextField(verbose_name="Descripción de la pieza")
    vehicle_make = models.CharField(max_length=100, verbose_name="Marca vehículo")
    vehicle_model = models.CharField(max_length=100, verbose_name="Modelo vehículo")
    vehicle_year = models.CharField(max_length=10, verbose_name="Año vehículo", blank=True)

    preferred_material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    reference_image = models.ImageField(upload_to="custom_orders/references/", blank=True, null=True)
    reference_file = models.FileField(upload_to="custom_orders/files/", blank=True, null=True,
                                      help_text="Plano, STL, o cualquier referencia")
    additional_notes = models.TextField(blank=True)

    # Respuesta interna
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido personalizado"
        verbose_name_plural = "Pedidos personalizados"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{str(self.id)[:8]} - {self.full_name} ({self.vehicle_make} {self.vehicle_model})"


# ─────────────────────────────────────────
# CARRITO
# ─────────────────────────────────────────
class Cart(models.Model):
    session_key = models.CharField(max_length=40, blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total(self):
        return sum(item.get_subtotal() for item in self.items.all())

    def get_item_count(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Carrito - {self.user or self.session_key}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    custom_notes = models.TextField(blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def get_unit_price(self):
        if self.variant:
            return self.variant.get_price()
        return self.product.base_price

    def get_subtotal(self):
        return self.get_unit_price() * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"


# ─────────────────────────────────────────
# ORDEN / PEDIDO
# ─────────────────────────────────────────
class Order(models.Model):
    STATUS_CHOICES = [
        ("pending_payment", "Pago pendiente"),
        ("paid", "Pagado"),
        ("in_production", "En producción"),
        ("shipped", "Enviado"),
        ("delivered", "Entregado"),
        ("cancelled", "Cancelado"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("webpay", "WebPay / Transbank"),
        ("mercadopago", "MercadoPago"),
        ("bank_transfer", "Transferencia bancaria"),
    ]
    NOTIFICATION_CHOICES = [
        ("whatsapp", "WhatsApp"),
        ("email", "Email"),
        ("both", "WhatsApp + Email"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Datos contacto/envío
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=50, default="Chile")

    # Pago
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, default="pending")
    payment_id = models.CharField(max_length=200, blank=True, help_text="ID transacción del gateway")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Notificación
    notification_method = models.CharField(max_length=10, choices=NOTIFICATION_CHOICES, default="email")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_payment")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orden"
        verbose_name_plural = "Órdenes"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_number:
            import random, string
            self.order_number = "GFX-" + "".join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)

    def get_subtotal(self):
        return sum(item.get_subtotal() for item in self.items.all())

    def __str__(self):
        return f"Orden {self.order_number} - {self.full_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)  # snapshot
    product_sku = models.CharField(max_length=50)    # snapshot
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    custom_notes = models.TextField(blank=True)

    def get_subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"


# ─────────────────────────────────────────
# PERFIL DE USUARIO
# ─────────────────────────────────────────
from django.contrib.auth.models import User as _User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user         = models.OneToOneField(_User, on_delete=models.CASCADE, related_name='profile')
    phone        = models.CharField(max_length=20, blank=True)
    address      = models.TextField(blank=True)
    city         = models.CharField(max_length=100, blank=True)
    region       = models.CharField(max_length=100, blank=True)
    postal_code  = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuarios'

    def __str__(self):
        return f'Perfil de {self.user.username}'


@receiver(post_save, sender=_User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


# ─────────────────────────────────────────
# CUPÓN DE DESCUENTO
# ─────────────────────────────────────────
class Coupon(models.Model):
    DISCOUNT_TYPE = [
        ('percent',  'Porcentaje (%)'),
        ('fixed',    'Monto fijo ($)'),
    ]
    code            = models.CharField(max_length=30, unique=True, verbose_name='Código')
    discount_type   = models.CharField(max_length=10, choices=DISCOUNT_TYPE, default='percent')
    discount_value  = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Valor descuento')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                           verbose_name='Monto mínimo de pedido')
    max_uses        = models.PositiveIntegerField(default=0, help_text='0 = ilimitado')
    uses            = models.PositiveIntegerField(default=0, verbose_name='Usos')
    active          = models.BooleanField(default=True)
    valid_from      = models.DateTimeField(null=True, blank=True)
    valid_until     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cupón'
        verbose_name_plural = 'Cupones'

    def __str__(self):
        return f'{self.code} — {self.discount_value}{"%" if self.discount_type == "percent" else "$"}'

    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.active:
            return False, 'Cupón inactivo.'
        if self.max_uses > 0 and self.uses >= self.max_uses:
            return False, 'Cupón agotado.'
        if self.valid_from and now < self.valid_from:
            return False, 'Cupón aún no válido.'
        if self.valid_until and now > self.valid_until:
            return False, 'Cupón expirado.'
        return True, 'ok'

    def calc_discount(self, subtotal):
        """Retorna el monto del descuento sobre el subtotal."""
        if self.discount_type == 'percent':
            return (subtotal * self.discount_value / 100).quantize(subtotal)
        return min(self.discount_value, subtotal)


# ─────────────────────────────────────────
# OPTIMIZACIÓN AUTOMÁTICA DE IMÁGENES
# ─────────────────────────────────────────
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image as PilImage

def _optimize_image(image_field, max_width=1200, quality=82):
    """Redimensiona y comprime una imagen al guardarla."""
    try:
        img = PilImage.open(image_field)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        if img.width > max_width:
            ratio = max_width / img.width
            new_h = int(img.height * ratio)
            img = img.resize((max_width, new_h), PilImage.LANCZOS)
        output = BytesIO()
        fmt = 'JPEG' if img.mode == 'RGB' else 'PNG'
        img.save(output, format=fmt, optimize=True, quality=quality)
        output.seek(0)
        name = image_field.name.rsplit('.', 1)[0] + ('.jpg' if fmt == 'JPEG' else '.png')
        image_field.save(name, ContentFile(output.read()), save=False)
    except Exception:
        pass  # nunca romper el guardado por error de imagen


@receiver(post_save, sender=Product)
def optimize_product_thumbnail(sender, instance, **kwargs):
    if instance.thumbnail:
        _optimize_image(instance.thumbnail, max_width=800, quality=80)


@receiver(post_save, sender=ProductImage)
def optimize_product_image(sender, instance, **kwargs):
    if instance.image:
        _optimize_image(instance.image, max_width=1200, quality=82)
