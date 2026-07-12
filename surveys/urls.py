"""Lumen URL configuration for surveys."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('forms/mine/', views.my_forms, name='my_forms'),
    path('forms/new/', views.form_create, name='form_create'),
    path('forms/<uuid:public_id>/manage/', views.form_manage, name='form_manage'),
    path('forms/<uuid:public_id>/publish/', views.form_publish, name='form_publish'),
    path('forms/<uuid:public_id>/close/', views.form_close, name='form_close'),
    path('forms/<uuid:public_id>/archive/', views.form_archive, name='form_archive'),
    path('forms/<uuid:public_id>/delete/', views.form_delete, name='form_delete'),
    path('forms/<uuid:public_id>/duplicate/', views.form_duplicate, name='form_duplicate'),
    path('forms/<uuid:public_id>/retry-sync/', views.form_retry_sync, name='form_retry_sync'),
    path(
        'forms/<uuid:public_id>/questions/<int:question_id>/edit/',
        views.question_edit,
        name='question_edit',
    ),
    path(
        'forms/<uuid:public_id>/questions/<int:question_id>/delete/',
        views.question_delete,
        name='question_delete',
    ),
    path('f/<uuid:public_id>/', views.form_detail, name='form_detail'),
    path('f/<uuid:public_id>/embed/', views.form_embed, name='form_embed'),
    path('f/<uuid:public_id>/thanks/', views.form_thanks, name='form_thanks'),
    path('f/<uuid:public_id>/responses/', views.form_responses, name='form_responses'),
    path(
        'f/<uuid:public_id>/responses/export/',
        views.form_responses_export,
        name='form_responses_export',
    ),
]
