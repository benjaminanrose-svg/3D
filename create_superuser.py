#!/usr/bin/env python
"""
Creates a Django superuser for the admin panel.
Run with: python create_superuser.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402 — must come after django.setup()

USERNAME = 'admin'
EMAIL = 'benjamin.an.ro.se@gmail.com'
PASSWORD = 'admin1314'

User = get_user_model()

if User.objects.filter(username=USERNAME).exists():
    print(f"User '{USERNAME}' already exists — deleting and recreating.")
    User.objects.filter(username=USERNAME).delete()

User.objects.create_superuser(username=USERNAME, email=EMAIL, password=PASSWORD)
print(f"Superuser '{USERNAME}' created successfully.")
