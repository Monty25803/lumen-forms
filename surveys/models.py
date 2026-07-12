"""Lumen survey models."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Form(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CLOSED = 'closed'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forms',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    google_sheet_id = models.CharField(max_length=128, blank=True)
    google_sheet_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_open_for_responses(self):
        if self.status != self.STATUS_PUBLISHED:
            return False
        if self.closes_at and timezone.now() >= self.closes_at:
            return False
        return True

    @property
    def is_listed_publicly(self):
        return self.status == self.STATUS_PUBLISHED

    def user_can_manage(self, user):
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return self.owner_id == user.id


class Question(models.Model):
    QUESTION_TYPES = (
        ('text', 'Short Text'),
        ('textarea', 'Long Text'),
        ('radio', 'Single Choice'),
        ('checkbox', 'Multiple Choice'),
        ('dropdown', 'Dropdown'),
    )
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='text')
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:50]

    @property
    def needs_options(self):
        return self.question_type in ('radio', 'checkbox', 'dropdown')


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text


class Response(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='responses')
    respondent_name = models.CharField(max_length=200)
    respondent_email = models.EmailField()
    respondent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='form_responses',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    synced_to_sheet = models.BooleanField(default=False)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Response from {self.respondent_email} to {self.form.title}'


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text_answer = models.TextField(blank=True)
    selected_options = models.ManyToManyField(Option, blank=True, related_name='answers')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['response', 'question'],
                name='unique_answer_per_response_question',
            ),
        ]

    def __str__(self):
        if self.text_answer:
            return self.text_answer[:50]
        return ', '.join(o.text for o in self.selected_options.all()[:3])
