"""Lumen survey views."""
import csv
import uuid
from collections import Counter
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET, require_POST

from .form_templates import FORM_TEMPLATES, apply_template
from .forms import FormCreateForm, FormMetaForm, QuestionBuilderForm, build_form_from_model
from .models import Answer, Form, Option, Question, Response
from .notify import notify_owner_of_response, retry_unsynced_responses
from .sheets import SheetsError, append_response_to_sheet, ensure_form_sheet, google_oauth_configured


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _rate_limit_exceeded(request):
    limit = getattr(settings, 'SUBMISSION_RATE_LIMIT', 20)
    window = getattr(settings, 'SUBMISSION_RATE_WINDOW_SECONDS', 3600)
    key = f'lumen-submit:{_client_ip(request)}'
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window)
    return False


def _can_preview(form_model, user):
    return form_model.user_can_manage(user)


def _choice_charts(form_model):
    charts = []
    choice_questions = form_model.questions.filter(
        question_type__in=('radio', 'checkbox', 'dropdown'),
    ).prefetch_related('options')
    for question in choice_questions:
        counter = Counter()
        for option in question.options.all():
            counter[option.text] = option.answers.count()
        total = sum(counter.values())
        charts.append({
            'question': question,
            'rows': [
                {
                    'label': label,
                    'count': count,
                    'pct': int(round((count / total) * 100)) if total else 0,
                }
                for label, count in counter.items()
            ],
            'total': total,
        })
    return charts


def _save_question_options(question, options):
    question.options.all().delete()
    for index, option_text in enumerate(options, start=1):
        Option.objects.create(question=question, text=option_text, order=index)


def home(request):
    public_forms = Form.objects.filter(status=Form.STATUS_PUBLISHED)
    my_forms = Form.objects.none()
    if request.user.is_authenticated:
        my_forms = Form.objects.filter(owner=request.user).exclude(status=Form.STATUS_ARCHIVED)
    return render(request, 'surveys/home.html', {
        'forms': public_forms,
        'my_forms': my_forms,
        'google_oauth_configured': google_oauth_configured(),
    })


@login_required
def my_forms(request):
    forms = Form.objects.filter(owner=request.user).exclude(status=Form.STATUS_ARCHIVED)
    return render(request, 'surveys/my_forms.html', {
        'forms': forms,
        'google_oauth_configured': google_oauth_configured(),
    })


@login_required
def form_create(request):
    if request.method == 'POST':
        form = FormCreateForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.owner = request.user
            survey.status = Form.STATUS_DRAFT
            title = (form.cleaned_data.get('title') or '').strip() or 'Untitled form'
            survey.title = title
            survey.save()
            apply_template(survey, form.cleaned_data['template_key'])
            messages.success(request, 'Draft created. Review questions, then publish.')
            return redirect('form_manage', public_id=survey.public_id)
    else:
        form = FormCreateForm()
    return render(request, 'surveys/form_create.html', {
        'form': form,
        'templates': FORM_TEMPLATES,
    })


@login_required
def form_manage(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')

    meta_form = FormMetaForm(instance=form_model)
    question_form = QuestionBuilderForm()
    pending_sync = form_model.responses.filter(synced_to_sheet=False).count()

    if request.method == 'POST':
        action = request.POST.get('action', 'save_meta')
        if action == 'save_meta':
            meta_form = FormMetaForm(request.POST, instance=form_model)
            if meta_form.is_valid():
                meta_form.save()
                messages.success(request, 'Form details saved.')
                return redirect('form_manage', public_id=public_id)
        elif action == 'add_question':
            question_form = QuestionBuilderForm(request.POST)
            if question_form.is_valid():
                order = (form_model.questions.count() + 1)
                question = Question.objects.create(
                    form=form_model,
                    text=question_form.cleaned_data['text'],
                    question_type=question_form.cleaned_data['question_type'],
                    required=question_form.cleaned_data['required'],
                    order=order,
                )
                _save_question_options(question, question_form.cleaned_data['options'])
                if form_model.google_sheet_id:
                    try:
                        ensure_form_sheet(request.user, form_model)
                    except SheetsError as exc:
                        messages.warning(request, str(exc))
                messages.success(request, 'Question added.')
                return redirect('form_manage', public_id=public_id)

    return render(request, 'surveys/form_manage.html', {
        'form_model': form_model,
        'meta_form': meta_form,
        'question_form': question_form,
        'questions': form_model.questions.prefetch_related('options'),
        'google_oauth_configured': google_oauth_configured(),
        'pending_sync': pending_sync,
        'share_url': request.build_absolute_uri(
            f'/f/{form_model.public_id}/'
        ),
        'embed_url': request.build_absolute_uri(
            f'/f/{form_model.public_id}/embed/'
        ),
    })


@login_required
def question_edit(request, public_id, question_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    question = get_object_or_404(Question, id=question_id, form=form_model)

    initial_options = list(question.options.values_list('text', flat=True))
    if request.method == 'POST':
        question_form = QuestionBuilderForm(request.POST)
        if question_form.is_valid():
            question.text = question_form.cleaned_data['text']
            question.question_type = question_form.cleaned_data['question_type']
            question.required = question_form.cleaned_data['required']
            question.save()
            _save_question_options(question, question_form.cleaned_data['options'])
            if form_model.google_sheet_id:
                try:
                    ensure_form_sheet(request.user, form_model)
                except SheetsError as exc:
                    messages.warning(request, str(exc))
            messages.success(request, 'Question updated.')
            return redirect('form_manage', public_id=public_id)
    else:
        question_form = QuestionBuilderForm(
            initial={
                'text': question.text,
                'question_type': question.question_type,
                'required': question.required,
            },
            initial_options=initial_options or ['', ''],
        )

    return render(request, 'surveys/question_edit.html', {
        'form_model': form_model,
        'question': question,
        'question_form': question_form,
    })


@login_required
@require_POST
def question_delete(request, public_id, question_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    question = get_object_or_404(Question, id=question_id, form=form_model)
    question.delete()
    messages.success(request, 'Question removed.')
    return redirect('form_manage', public_id=public_id)


@login_required
@require_POST
def form_publish(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    if not form_model.questions.exists():
        messages.error(request, 'Add at least one question before publishing.')
        return redirect('form_manage', public_id=public_id)

    missing_options = [
        q for q in form_model.questions.all()
        if q.needs_options and q.options.count() < 2
    ]
    if missing_options:
        messages.error(request, 'Every choice question needs at least two options.')
        return redirect('form_manage', public_id=public_id)

    try:
        ensure_form_sheet(request.user, form_model)
    except SheetsError as exc:
        msg = str(exc)
        if 'expired' in msg.lower() or 'connect google' in msg.lower():
            messages.error(
                request,
                f'{msg} Reconnect Google from the Sign in page, then try again.',
            )
        else:
            messages.error(request, msg)
        return redirect('form_manage', public_id=public_id)

    form_model.status = Form.STATUS_PUBLISHED
    form_model.save(update_fields=['status', 'updated_at'])
    messages.success(
        request,
        'Published successfully. Copy your share link below — answers go to your Google Sheet.',
    )
    return redirect('form_manage', public_id=public_id)


@login_required
@require_POST
def form_close(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    form_model.status = Form.STATUS_CLOSED
    form_model.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Form closed. New responses are blocked.')
    return redirect('form_manage', public_id=public_id)


@login_required
@require_POST
def form_archive(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    form_model.status = Form.STATUS_ARCHIVED
    form_model.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Form archived.')
    return redirect('my_forms')


@login_required
@require_POST
def form_delete(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    form_model.delete()
    messages.success(request, 'Form deleted.')
    return redirect('my_forms')


@login_required
@require_POST
def form_duplicate(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')

    with transaction.atomic():
        clone = Form.objects.create(
            owner=request.user,
            title=f'{form_model.title} (copy)',
            description=form_model.description,
            status=Form.STATUS_DRAFT,
            closes_at=form_model.closes_at,
            public_id=uuid.uuid4(),
        )
        for question in form_model.questions.prefetch_related('options'):
            new_q = Question.objects.create(
                form=clone,
                text=question.text,
                question_type=question.question_type,
                required=question.required,
                order=question.order,
            )
            for option in question.options.all():
                Option.objects.create(
                    question=new_q,
                    text=option.text,
                    order=option.order,
                )
    messages.success(request, 'Form duplicated as a draft.')
    return redirect('form_manage', public_id=clone.public_id)


@login_required
@require_POST
def form_retry_sync(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('You do not own this form.')
    synced, failed = retry_unsynced_responses(form_model)
    if synced and not failed:
        messages.success(request, f'Synced {synced} response(s) to Google Sheets.')
    elif synced:
        messages.warning(request, f'Synced {synced}, but {failed} still failed.')
    else:
        messages.error(
            request,
            'Could not sync responses. Reconnect Google if access expired, then retry.',
        )
    return redirect('form_responses', public_id=public_id)


def form_detail(request, public_id, embed=False):
    form_model = get_object_or_404(Form, public_id=public_id)
    can_manage = _can_preview(form_model, request.user)

    if form_model.status == Form.STATUS_ARCHIVED and not can_manage:
        return HttpResponseForbidden('This form is no longer available.')
    if form_model.status == Form.STATUS_DRAFT and not can_manage:
        return HttpResponseForbidden('This form is not published yet.')

    can_submit = form_model.is_open_for_responses
    form_class, initials = build_form_from_model(form_model, user=request.user)
    form = form_class(initial=initials)

    if request.method == 'POST':
        if not can_submit:
            messages.error(request, 'This form is not accepting responses.')
            return redirect('form_embed' if embed else 'form_detail', public_id=public_id)

        if _rate_limit_exceeded(request):
            messages.error(request, 'Too many submissions. Please try again later.')
            return redirect('form_embed' if embed else 'form_detail', public_id=public_id)

        form = form_class(request.POST)
        if form.is_valid():
            questions = {
                q.id: q
                for q in form_model.questions.prefetch_related('options')
            }
            if not questions:
                messages.error(request, 'This form has no questions yet.')
                return redirect('form_embed' if embed else 'form_detail', public_id=public_id)

            try:
                with transaction.atomic():
                    response = Response.objects.create(
                        form=form_model,
                        respondent_name=form.cleaned_data['respondent_name'].strip(),
                        respondent_email=form.cleaned_data['respondent_email'].strip(),
                        respondent_user=request.user if request.user.is_authenticated else None,
                    )
                    for key, value in form.cleaned_data.items():
                        if key in ('website', 'respondent_name', 'respondent_email'):
                            continue
                        if not key.startswith('question_'):
                            continue
                        if value is None or value == '' or value == []:
                            continue
                        question_id = int(key.split('_', 1)[1])
                        question = questions.get(question_id)
                        if question is None:
                            continue
                        answer = Answer.objects.create(response=response, question=question)
                        if question.question_type in ('radio', 'dropdown'):
                            option = Option.objects.filter(
                                id=int(value),
                                question=question,
                            ).first()
                            if option is None:
                                raise Option.DoesNotExist
                            answer.selected_options.add(option)
                        elif question.question_type == 'checkbox':
                            options = list(
                                Option.objects.filter(
                                    id__in=[int(opt_id) for opt_id in value],
                                    question=question,
                                )
                            )
                            if len(options) != len(value):
                                raise Option.DoesNotExist
                            answer.selected_options.add(*options)
                        else:
                            answer.text_answer = str(value)
                            answer.save()
            except (Option.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'Invalid answer submitted. Please try again.')
                return redirect('form_embed' if embed else 'form_detail', public_id=public_id)

            append_response_to_sheet(form_model, response)
            notify_owner_of_response(form_model, response, request=request)
            return redirect('form_thanks', public_id=public_id)

    template = 'surveys/form_embed.html' if embed else 'surveys/form_detail.html'
    return render(request, template, {
        'form_model': form_model,
        'form': form,
        'can_submit': can_submit,
        'can_manage': can_manage and not embed,
        'embed': embed,
    })


@xframe_options_exempt
def form_embed(request, public_id):
    return form_detail(request, public_id, embed=True)


def form_thanks(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    return render(request, 'surveys/form_thanks.html', {'form_model': form_model})


def _response_rows(form_model):
    questions = list(form_model.questions.all())
    responses = form_model.responses.all().prefetch_related(
        'answers__question',
        'answers__selected_options',
    )
    rows = []
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
        rows.append((response, answer_list))
    return questions, rows


@login_required
def form_responses(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('Only the form owner can view responses.')
    questions, rows = _response_rows(form_model)
    paginator = Paginator(rows, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    pending_sync = form_model.responses.filter(synced_to_sheet=False).count()
    return render(request, 'surveys/form_responses.html', {
        'form_model': form_model,
        'questions': questions,
        'page_obj': page_obj,
        'total_responses': paginator.count,
        'charts': _choice_charts(form_model),
        'pending_sync': pending_sync,
    })


@login_required
@require_GET
def form_responses_export(request, public_id):
    form_model = get_object_or_404(Form, public_id=public_id)
    if not form_model.user_can_manage(request.user):
        return HttpResponseForbidden('Only the form owner can export responses.')
    questions, rows = _response_rows(form_model)

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['#', 'Submitted', 'Name', 'Email'] + [q.text for q in questions])
    for index, (response, answer_list) in enumerate(rows, start=1):
        writer.writerow(
            [
                index,
                response.submitted_at.isoformat(timespec='seconds'),
                response.respondent_name,
                response.respondent_email,
            ] + answer_list
        )

    download = HttpResponse(buffer.getvalue(), content_type='text/csv')
    download['Content-Disposition'] = (
        f'attachment; filename="lumen-{form_model.public_id}-responses.csv"'
    )
    return download
