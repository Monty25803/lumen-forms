"""Dynamic fill forms and builder forms for Lumen."""
from django import forms

from .models import Form, Question


class HoneypotFormMixin:
    """Invisible field that bots tend to fill; humans should leave blank."""

    def add_honeypot(self):
        self.fields['website'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'honeypot-field',
                'tabindex': '-1',
                'autocomplete': 'off',
                'aria-hidden': 'true',
            }),
            label='',
        )

    def clean_website(self):
        value = self.cleaned_data.get('website')
        if value:
            raise forms.ValidationError('Invalid submission.')
        return value


def _build_field(question):
    required = question.required

    if question.question_type == 'text':
        return forms.CharField(
            max_length=500,
            required=required,
            label=question.text,
            widget=forms.TextInput(attrs={
                'class': 'lumen-input',
                'placeholder': 'Your answer',
            }),
        )
    if question.question_type == 'textarea':
        return forms.CharField(
            required=required,
            label=question.text,
            widget=forms.Textarea(attrs={
                'class': 'lumen-input lumen-textarea',
                'placeholder': 'Your answer',
                'rows': 4,
            }),
        )
    if question.question_type in ('radio', 'dropdown'):
        choices = [(opt.id, opt.text) for opt in question.options.all()]
        if question.question_type == 'radio':
            widget = forms.RadioSelect(attrs={'class': 'lumen-radio'})
        else:
            widget = forms.Select(attrs={'class': 'lumen-select'})
        return forms.ChoiceField(
            choices=choices,
            required=required,
            label=question.text,
            widget=widget,
        )
    if question.question_type == 'checkbox':
        choices = [(opt.id, opt.text) for opt in question.options.all()]
        return forms.MultipleChoiceField(
            choices=choices,
            required=required,
            label=question.text,
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'lumen-checkbox'}),
        )
    return forms.CharField(
        required=required,
        label=question.text,
        widget=forms.TextInput(attrs={'class': 'lumen-input'}),
    )


def build_form_from_model(form_model, user=None):
    """Build a Django form dynamically from a Form model instance."""
    questions = list(form_model.questions.prefetch_related('options'))
    initial_name = ''
    initial_email = ''
    if user is not None and getattr(user, 'is_authenticated', False):
        initial_name = (user.get_full_name() or user.get_username() or '').strip()
        initial_email = (user.email or '').strip()

    class DynamicForm(HoneypotFormMixin, forms.Form):
        respondent_name = forms.CharField(
            max_length=200,
            label='Your name',
            widget=forms.TextInput(attrs={
                'class': 'lumen-input',
                'placeholder': 'Full name',
                'autocomplete': 'name',
            }),
        )
        respondent_email = forms.EmailField(
            label='Your email',
            widget=forms.EmailInput(attrs={
                'class': 'lumen-input',
                'placeholder': 'you@example.com',
                'autocomplete': 'email',
            }),
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for question in questions:
                self.fields[f'question_{question.id}'] = _build_field(question)
            self.add_honeypot()

    return DynamicForm, {'respondent_name': initial_name, 'respondent_email': initial_email}


class FormMetaForm(forms.ModelForm):
    class Meta:
        model = Form
        fields = ('title', 'description', 'closes_at')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'lumen-input',
                'placeholder': 'Form title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'lumen-input lumen-textarea',
                'rows': 3,
                'placeholder': 'Optional description for people filling this form',
            }),
            'closes_at': forms.DateTimeInput(attrs={
                'class': 'lumen-input',
                'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['closes_at'].required = False
        self.fields['closes_at'].label = 'Close submissions at'
        self.fields['closes_at'].help_text = 'Optional. After this time, the form stops accepting answers.'
        if self.instance and self.instance.closes_at:
            self.initial['closes_at'] = self.instance.closes_at.strftime('%Y-%m-%dT%H:%M')


class FormCreateForm(FormMetaForm):
    template_key = forms.ChoiceField(
        choices=[],
        required=True,
        label='Starter template',
        widget=forms.Select(attrs={'class': 'lumen-select'}),
    )

    def __init__(self, *args, **kwargs):
        from .form_templates import FORM_TEMPLATES
        super().__init__(*args, **kwargs)
        self.fields['template_key'].choices = [
            (key, f"{meta['label']} — {meta['description']}")
            for key, meta in FORM_TEMPLATES.items()
        ]
        self.fields['title'].required = False
        self.fields['title'].initial = 'Untitled form'


class QuestionBuilderForm(forms.Form):
    text = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'lumen-input',
            'placeholder': 'Question text',
        }),
    )
    question_type = forms.ChoiceField(
        choices=Question.QUESTION_TYPES,
        widget=forms.Select(attrs={
            'class': 'lumen-select',
            'id': 'id_question_type',
        }),
    )
    required = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, initial_options=None, **kwargs):
        super().__init__(*args, **kwargs)
        raw_options = []
        if self.data is not None:
            raw_options = [v.strip() for v in self.data.getlist('options') if str(v).strip()]
        elif initial_options:
            raw_options = list(initial_options)
        if not raw_options:
            raw_options = ['', '']
        while len(raw_options) < 2:
            raw_options.append('')
        self.option_values = raw_options

    def clean(self):
        cleaned = super().clean()
        question_type = cleaned.get('question_type')
        options = []
        if self.data is not None:
            options = [v.strip() for v in self.data.getlist('options') if str(v).strip()]
        if question_type in ('radio', 'checkbox', 'dropdown'):
            if len(options) < 2:
                self.add_error(None, 'Add at least two options for this question type.')
            cleaned['options'] = options
        else:
            cleaned['options'] = []
        return cleaned
