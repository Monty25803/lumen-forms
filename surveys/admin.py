"""Lumen admin configuration."""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Answer, Form, Option, Question, Response


class OptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ('text', 'order')


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    fields = ('text', 'question_type', 'required', 'order')
    show_change_link = True


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'public_id', 'closes_at', 'created_at', 'open_link')
    list_filter = ('status',)
    search_fields = ('title', 'description', 'public_id', 'owner__username', 'owner__email')
    readonly_fields = ('public_id', 'created_at', 'updated_at', 'share_url', 'google_sheet_id', 'google_sheet_url')
    raw_id_fields = ('owner',)
    inlines = [QuestionInline]
    fieldsets = (
        (None, {
            'fields': ('owner', 'title', 'description', 'status', 'closes_at'),
        }),
        ('Sharing', {
            'fields': ('public_id', 'share_url'),
        }),
        ('Google Sheet', {
            'fields': ('google_sheet_id', 'google_sheet_url'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Public link')
    def open_link(self, obj):
        url = reverse('form_detail', args=[obj.public_id])
        return format_html('<a href="{}" target="_blank">Open</a>', url)

    @admin.display(description='Share URL path')
    def share_url(self, obj):
        return reverse('form_detail', args=[obj.public_id])


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'form', 'question_type', 'required', 'order', 'option_count')
    list_filter = ('form', 'question_type', 'required')
    search_fields = ('text',)
    inlines = [OptionInline]

    @admin.display(description='Options')
    def option_count(self, obj):
        count = obj.options.count()
        if obj.needs_options and count == 0:
            return format_html('<span style="color:#c00;">0 — add options</span>')
        return count


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'text_answer')
    fields = ('question', 'text_answer')


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('form', 'respondent_name', 'respondent_email', 'submitted_at', 'synced_to_sheet')
    list_filter = ('form', 'synced_to_sheet')
    search_fields = ('respondent_name', 'respondent_email')
    inlines = [AnswerInline]


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'order')
    list_filter = ('question__form',)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('response', 'question', 'text_answer')
    list_filter = ('question__form',)
