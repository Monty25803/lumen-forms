"""Lumen URL configuration."""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Lumen Admin'
admin.site.site_title = 'Lumen'
admin.site.index_title = 'Site administration'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('surveys.urls')),
]
