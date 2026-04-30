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


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
