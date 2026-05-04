from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from store.sitemaps import ProductSitemap, CategorySitemap, StaticSitemap

sitemaps = {
    'products':   ProductSitemap,
    'categories': CategorySitemap,
    'static':     StaticSitemap,
}

def robots_txt(request):
    host = getattr(settings, 'SITE_DOMAIN', 'gflex3d.cl')
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /carrito/",
        "Disallow: /checkout/",
        f"Sitemap: https://{host}/sitemap.xml",
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def health_check(request):
    return HttpResponse('OK', status=200)


def debug_view(request):
    import os, traceback
    try:
        static_root = str(settings.STATIC_ROOT)
        static_exists = os.path.exists(static_root)
        static_files = os.listdir(static_root)[:5] if static_exists else []
        from store.models import Product, Category
        products = Product.objects.count()
        categories = Category.objects.count()
        info = (
            f"App OK\n"
            f"DEBUG={settings.DEBUG}\n"
            f"STATIC_ROOT={static_root} exists={static_exists}\n"
            f"Static files sample: {static_files}\n"
            f"Products: {products}, Categories: {categories}\n"
        )
        return HttpResponse(info, content_type='text/plain')
    except Exception as e:
        return HttpResponse(f"ERROR:\n{traceback.format_exc()}", content_type='text/plain', status=500)


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('debug-info/', debug_view, name='debug_view'),
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
