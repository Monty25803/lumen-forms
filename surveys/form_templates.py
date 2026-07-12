"""Built-in starter form templates."""

FORM_TEMPLATES = {
    'blank': {
        'label': 'Blank form',
        'description': 'Start from scratch.',
        'questions': [],
    },
    'feedback': {
        'label': 'Customer feedback',
        'description': 'Collect ratings and comments.',
        'form_title': 'Customer feedback',
        'form_description': 'Tell us how we did.',
        'questions': [
            {'text': 'How was your experience?', 'question_type': 'radio', 'required': True,
             'options': ['Excellent', 'Good', 'Average', 'Poor']},
            {'text': 'What did you like?', 'question_type': 'checkbox', 'required': False,
             'options': ['Support', 'Speed', 'Design', 'Price']},
            {'text': 'Any other comments?', 'question_type': 'textarea', 'required': False, 'options': []},
        ],
    },
    'rsvp': {
        'label': 'Event RSVP',
        'description': 'Track attendance for an event.',
        'form_title': 'Event RSVP',
        'form_description': 'Please confirm your attendance.',
        'questions': [
            {'text': 'Will you attend?', 'question_type': 'radio', 'required': True,
             'options': ['Yes', 'No', 'Maybe']},
            {'text': 'Number of guests', 'question_type': 'dropdown', 'required': True,
             'options': ['1', '2', '3', '4+']},
            {'text': 'Dietary notes', 'question_type': 'textarea', 'required': False, 'options': []},
        ],
    },
    'pulse': {
        'label': 'Team pulse',
        'description': 'Quick weekly check-in.',
        'form_title': 'Team pulse',
        'form_description': 'A short weekly check-in.',
        'questions': [
            {'text': 'How are you feeling this week?', 'question_type': 'radio', 'required': True,
             'options': ['Great', 'Okay', 'Stressed', 'Burned out']},
            {'text': 'Biggest win', 'question_type': 'text', 'required': False, 'options': []},
            {'text': 'Biggest blocker', 'question_type': 'textarea', 'required': False, 'options': []},
        ],
    },
}


def apply_template(form, template_key):
    from .models import Option, Question

    template = FORM_TEMPLATES.get(template_key) or FORM_TEMPLATES['blank']
    if template.get('form_title') and form.title in ('', 'Untitled form'):
        form.title = template['form_title']
    if template.get('form_description') and not form.description:
        form.description = template['form_description']
    form.save()

    for index, spec in enumerate(template.get('questions', []), start=1):
        question = Question.objects.create(
            form=form,
            text=spec['text'],
            question_type=spec['question_type'],
            required=spec.get('required', True),
            order=index,
        )
        for opt_index, option_text in enumerate(spec.get('options', []), start=1):
            Option.objects.create(question=question, text=option_text, order=opt_index)
    return form
