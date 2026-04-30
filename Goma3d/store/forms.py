from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomOrderRequest, Material, UserProfile

REGIONES = [
    ('', 'Selecciona región...'),
    ('Arica y Parinacota', 'Arica y Parinacota'),
    ('Tarapacá', 'Tarapacá'),
    ('Antofagasta', 'Antofagasta'),
    ('Atacama', 'Atacama'),
    ('Coquimbo', 'Coquimbo'),
    ('Valparaíso', 'Valparaíso'),
    ('Metropolitana de Santiago', 'Metropolitana de Santiago'),
    ("O'Higgins", "O'Higgins"),
    ('Maule', 'Maule'),
    ('Ñuble', 'Ñuble'),
    ('Biobío', 'Biobío'),
    ('La Araucanía', 'La Araucanía'),
    ('Los Ríos', 'Los Ríos'),
    ('Los Lagos', 'Los Lagos'),
    ('Aysén', 'Aysén'),
    ('Magallanes', 'Magallanes'),
]

PAYMENT_CHOICES = [
    ('bank_transfer', 'Transferencia bancaria'),
    ('mercadopago', 'MercadoPago'),
    ('webpay', 'WebPay / Transbank'),
]

NOTIFICATION_CHOICES = [
    ('email', 'Email'),
    ('whatsapp', 'WhatsApp'),
    ('both', 'WhatsApp + Email'),
]


class CheckoutForm(forms.Form):
    full_name           = forms.CharField(max_length=200)
    email               = forms.EmailField()
    phone               = forms.CharField(max_length=20)
    address             = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))
    city                = forms.CharField(max_length=100)
    region              = forms.ChoiceField(choices=REGIONES)
    postal_code         = forms.CharField(max_length=10, required=False)
    payment_method      = forms.ChoiceField(choices=PAYMENT_CHOICES, widget=forms.RadioSelect)
    notification_method = forms.ChoiceField(choices=NOTIFICATION_CHOICES, widget=forms.RadioSelect)
    notes               = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)


class CustomOrderForm(forms.ModelForm):
    class Meta:
        model  = CustomOrderRequest
        fields = ['full_name', 'email', 'phone',
                  'vehicle_make', 'vehicle_model', 'vehicle_year',
                  'part_description', 'preferred_material', 'quantity',
                  'reference_image', 'additional_notes']
        widgets = {
            'part_description':  forms.Textarea(attrs={'rows': 3}),
            'additional_notes':  forms.Textarea(attrs={'rows': 2}),
        }


# ── AUTH ──────────────────────────────────────────────────────────────────────

class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Email o usuario',
                               widget=forms.TextInput(attrs={'placeholder': 'tu@email.cl'}))
    password = forms.CharField(label='Contraseña',
                               widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}))


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label='Contraseña',
                                widget=forms.PasswordInput(attrs={'placeholder': 'Mínimo 8 caracteres'}))
    password2 = forms.CharField(label='Confirmar contraseña',
                                widget=forms.PasswordInput(attrs={'placeholder': 'Repite la contraseña'}))

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email', 'username']
        labels = {
            'first_name': 'Nombre',
            'last_name':  'Apellido',
            'email':      'Email',
            'username':   'Nombre de usuario',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este email.')
        return email

    def clean(self):
        cd = super().clean()
        if cd.get('password1') != cd.get('password2'):
            self.add_error('password2', 'Las contraseñas no coinciden.')
        return cd

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='Nombre')
    last_name  = forms.CharField(max_length=150, label='Apellido', required=False)
    email      = forms.EmailField(label='Email')

    class Meta:
        model  = UserProfile
        fields = ['phone', 'address', 'city', 'region', 'postal_code']
        labels = {
            'phone':       'Teléfono',
            'address':     'Dirección',
            'city':        'Ciudad',
            'region':      'Región',
            'postal_code': 'Código postal',
        }
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'region':  forms.Select(choices=REGIONES),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial  = self.user.last_name
            self.fields['email'].initial      = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name  = self.cleaned_data['last_name']
            self.user.email      = self.cleaned_data['email']
            if commit:
                self.user.save()
        if commit:
            profile.save()
        return profile


class CouponForm(forms.Form):
    code = forms.CharField(
        max_length=30,
        required=False,
        label='Cupón de descuento',
        widget=forms.TextInput(attrs={'placeholder': 'CÓDIGO', 'style': 'text-transform:uppercase'}),
    )

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            return code
        from .models import Coupon
        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            raise forms.ValidationError('Cupón no encontrado.')
        valid, msg = coupon.is_valid()
        if not valid:
            raise forms.ValidationError(msg)
        return code
