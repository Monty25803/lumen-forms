"""
Neon's Form - Views for form listing, creation, and response
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Form, Question, Option, Response, Answer
from .forms import build_form_from_model


def home(request):
    """List all forms."""
    forms = Form.objects.all()
    return render(request, 'forms_app/home.html', {'forms': forms})


def form_detail(request, form_id):
    """Display a form for filling out."""
    form_model = get_object_or_404(Form, id=form_id)
    form_class = build_form_from_model(form_model)

    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            response = Response.objects.create(form=form_model)
            for key, value in form.cleaned_data.items():
                if not key.startswith('question_') or value is None or value == '' or value == []:
                    continue
                question_id = int(key.split('_')[1])
                question = Question.objects.get(id=question_id)
                answer = Answer.objects.create(
                    response=response,
                    question=question
                )
                if question.question_type in ('radio', 'dropdown'):
                    answer.selected_options.add(Option.objects.get(id=int(value)))
                elif question.question_type == 'checkbox':
                    for opt_id in value:
                        answer.selected_options.add(Option.objects.get(id=int(opt_id)))
                else:
                    answer.text_answer = str(value)
                    answer.save()
            return redirect('form_thanks', form_id=form_id)
    else:
        form = form_class()

    return render(request, 'forms_app/form_detail.html', {
        'form_model': form_model,
        'form': form,
    })


def form_thanks(request, form_id):
    """Thank you page after form submission."""
    form_model = get_object_or_404(Form, id=form_id)
    return render(request, 'forms_app/form_thanks.html', {'form_model': form_model})


@staff_member_required(login_url='admin:login')
def form_responses(request, form_id):
    """View responses for a form (simple admin view)."""
    form_model = get_object_or_404(Form, id=form_id)
    responses = form_model.responses.all().prefetch_related('answers__question', 'answers__selected_options')
    # Build response rows: list of (response, [answer_text per question in order])
    questions = list(form_model.questions.all())
    response_rows = []
    for response in responses:
        answers_by_question = {}
        for answer in response.answers.all():
            if answer.text_answer:
                answers_by_question[answer.question_id] = answer.text_answer
            else:
                answers_by_question[answer.question_id] = ', '.join(
                    o.text for o in answer.selected_options.all()
                )
        answer_list = [answers_by_question.get(q.id, '') for q in questions]
        response_rows.append((response, answer_list))
    return render(request, 'forms_app/form_responses.html', {
        'form_model': form_model,
        'response_rows': response_rows,
    })
