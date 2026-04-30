from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority   = 0.9

    def items(self):
        return Product.objects.filter(status='active')

    def location(self, obj):
        return reverse('product_detail', args=[obj.slug])

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority   = 0.7

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return reverse('catalog_category', args=[obj.slug])


class StaticSitemap(Sitemap):
    changefreq = 'monthly'
    priority   = 0.5

    def items(self):
        return ['home', 'catalog', 'custom_order']

    def location(self, item):
        return reverse(item)
