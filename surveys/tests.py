from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Answer, Form, Option, Question, Response


class FormWorkflowTests(TestCase):
    def setUp(self):
        Site.objects.update_or_create(id=1, defaults={'domain': 'testserver', 'name': 'Lumen'})
        self.owner = get_user_model().objects.create_user(
            username='owner',
            email='owner@example.com',
            password='password',
        )
        self.form = Form.objects.create(
            owner=self.owner,
            title='Customer feedback',
            description='Tell us what you think.',
            status=Form.STATUS_PUBLISHED,
            google_sheet_id='sheet-123',
            google_sheet_url='https://docs.google.com/spreadsheets/d/sheet-123/edit',
        )
        self.name_question = Question.objects.create(
            form=self.form,
            text='Your name',
            question_type='text',
            order=1,
        )
        self.rating_question = Question.objects.create(
            form=self.form,
            text='How was your experience?',
            question_type='radio',
            order=2,
        )
        self.good_option = Option.objects.create(
            question=self.rating_question,
            text='Good',
            order=1,
        )
        Option.objects.create(question=self.rating_question, text='Bad', order=2)
        self.comment_question = Question.objects.create(
            form=self.form,
            text='Comments',
            question_type='textarea',
            required=False,
            order=3,
        )
        self.topics_question = Question.objects.create(
            form=self.form,
            text='Topics',
            question_type='checkbox',
            required=False,
            order=4,
        )
        self.topic_a = Option.objects.create(question=self.topics_question, text='Design', order=1)
        Option.objects.create(question=self.topics_question, text='Speed', order=2)
        self.channel_question = Question.objects.create(
            form=self.form,
            text='Channel',
            question_type='dropdown',
            order=5,
        )
        self.channel_web = Option.objects.create(
            question=self.channel_question,
            text='Web',
            order=1,
        )

    @patch('surveys.views.append_response_to_sheet', return_value=True)
    def test_public_user_can_submit_form(self, _mock_sheet):
        response = self.client.post(
            reverse('form_detail', args=[self.form.public_id]),
            {
                'respondent_name': 'Alex Rivera',
                'respondent_email': 'alex@example.com',
                f'question_{self.name_question.id}': 'Alex',
                f'question_{self.rating_question.id}': str(self.good_option.id),
                f'question_{self.comment_question.id}': 'Great product',
                f'question_{self.topics_question.id}': [str(self.topic_a.id)],
                f'question_{self.channel_question.id}': str(self.channel_web.id),
                'website': '',
            },
        )

        self.assertRedirects(response, reverse('form_thanks', args=[self.form.public_id]))
        stored_response = Response.objects.get(form=self.form)
        self.assertEqual(stored_response.respondent_name, 'Alex Rivera')
        self.assertEqual(stored_response.respondent_email, 'alex@example.com')
        text_answer = Answer.objects.get(response=stored_response, question=self.name_question)
        self.assertEqual(text_answer.text_answer, 'Alex')
        _mock_sheet.assert_called_once()

    def test_owner_can_create_and_manage_form(self):
        self.client.force_login(self.owner)
        create = self.client.post(reverse('form_create'), {
            'title': 'Meetup RSVP',
            'description': 'Are you coming?',
            'template_key': 'blank',
        })
        survey = Form.objects.get(title='Meetup RSVP')
        self.assertEqual(survey.owner, self.owner)
        self.assertRedirects(create, reverse('form_manage', args=[survey.public_id]))

        add = self.client.post(reverse('form_manage', args=[survey.public_id]), {
            'action': 'add_question',
            'text': 'Your name',
            'question_type': 'text',
            'required': 'on',
        })
        self.assertRedirects(add, reverse('form_manage', args=[survey.public_id]))
        self.assertEqual(survey.questions.count(), 1)

        choice = self.client.post(reverse('form_manage', args=[survey.public_id]), {
            'action': 'add_question',
            'text': 'Pick one',
            'question_type': 'radio',
            'required': 'on',
            'options': ['Yes', 'No', 'Maybe'],
        })
        self.assertRedirects(choice, reverse('form_manage', args=[survey.public_id]))
        question = survey.questions.get(text='Pick one')
        self.assertEqual(
            list(question.options.values_list('text', flat=True)),
            ['Yes', 'No', 'Maybe'],
        )

    @patch('surveys.views.ensure_form_sheet')
    def test_owner_can_publish(self, mock_ensure):
        mock_ensure.side_effect = lambda user, form: form
        self.client.force_login(self.owner)
        draft = Form.objects.create(owner=self.owner, title='Draft form', status=Form.STATUS_DRAFT)
        Question.objects.create(form=draft, text='Hello', question_type='text', order=1)

        response = self.client.post(reverse('form_publish', args=[draft.public_id]))
        draft.refresh_from_db()
        self.assertRedirects(response, reverse('form_manage', args=[draft.public_id]))
        self.assertEqual(draft.status, Form.STATUS_PUBLISHED)
        mock_ensure.assert_called_once()

    def test_home_hides_drafts_from_public(self):
        Form.objects.create(owner=self.owner, title='Secret draft', status=Form.STATUS_DRAFT)
        response = self.client.get(reverse('home'))
        self.assertContains(response, self.form.title)
        self.assertNotContains(response, 'Secret draft')
        self.assertNotContains(response, reverse('form_responses', args=[self.form.public_id]))

    def test_draft_form_forbidden_for_public(self):
        draft = Form.objects.create(owner=self.owner, title='Draft only', status=Form.STATUS_DRAFT)
        response = self.client.get(reverse('form_detail', args=[draft.public_id]))
        self.assertEqual(response.status_code, 403)

    def test_closed_form_rejects_submissions(self):
        self.form.status = Form.STATUS_CLOSED
        self.form.save()
        response = self.client.post(
            reverse('form_detail', args=[self.form.public_id]),
            {
                'respondent_name': 'Alex',
                'respondent_email': 'alex@example.com',
                f'question_{self.name_question.id}': 'Alex',
                f'question_{self.rating_question.id}': str(self.good_option.id),
                f'question_{self.channel_question.id}': str(self.channel_web.id),
                'website': '',
            },
        )
        self.assertRedirects(response, reverse('form_detail', args=[self.form.public_id]))
        self.assertEqual(Response.objects.count(), 0)

    def test_response_view_requires_owner(self):
        response = self.client.get(reverse('form_responses', args=[self.form.public_id]))
        self.assertEqual(response.status_code, 302)

        stranger = get_user_model().objects.create_user(
            username='stranger',
            email='stranger@example.com',
            password='password',
        )
        self.client.force_login(stranger)
        forbidden = self.client.get(reverse('form_responses', args=[self.form.public_id]))
        self.assertEqual(forbidden.status_code, 403)

    def test_owner_can_view_results_and_export(self):
        Response.objects.create(
            form=self.form,
            respondent_name='Alex Rivera',
            respondent_email='alex@example.com',
        )
        self.client.force_login(self.owner)
        responses_response = self.client.get(reverse('form_responses', args=[self.form.public_id]))
        export_response = self.client.get(
            reverse('form_responses_export', args=[self.form.public_id])
        )
        self.assertContains(responses_response, 'Customer feedback')
        self.assertContains(responses_response, 'Alex Rivera')
        self.assertContains(responses_response, 'alex@example.com')
        self.assertContains(responses_response, '1 response(s)')
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response['Content-Type'], 'text/csv')
        self.assertIn(b'Name', export_response.content)
        self.assertIn(b'Email', export_response.content)

    def test_required_field_validation(self):
        response = self.client.post(
            reverse('form_detail', args=[self.form.public_id]),
            {
                'respondent_name': 'Alex',
                'respondent_email': 'alex@example.com',
                f'question_{self.rating_question.id}': str(self.good_option.id),
                f'question_{self.channel_question.id}': str(self.channel_web.id),
                'website': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Response.objects.count(), 0)

    def test_respondent_identity_required(self):
        response = self.client.post(
            reverse('form_detail', args=[self.form.public_id]),
            {
                f'question_{self.name_question.id}': 'Alex',
                f'question_{self.rating_question.id}': str(self.good_option.id),
                f'question_{self.channel_question.id}': str(self.channel_web.id),
                'website': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Response.objects.count(), 0)

    def test_honeypot_blocks_bots(self):
        response = self.client.post(
            reverse('form_detail', args=[self.form.public_id]),
            {
                'respondent_name': 'Bot',
                'respondent_email': 'bot@example.com',
                f'question_{self.name_question.id}': 'Bot',
                f'question_{self.rating_question.id}': str(self.good_option.id),
                f'question_{self.channel_question.id}': str(self.channel_web.id),
                'website': 'http://spam.example',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Response.objects.count(), 0)

    def test_closes_at_blocks_submissions(self):
        self.form.closes_at = timezone.now() - timezone.timedelta(minutes=1)
        self.form.save()
        response = self.client.post(
            reverse('form_detail', args=[self.form.public_id]),
            {
                'respondent_name': 'Alex',
                'respondent_email': 'alex@example.com',
                f'question_{self.name_question.id}': 'Alex',
                f'question_{self.rating_question.id}': str(self.good_option.id),
                f'question_{self.channel_question.id}': str(self.channel_web.id),
                'website': '',
            },
        )
        self.assertRedirects(response, reverse('form_detail', args=[self.form.public_id]))
        self.assertEqual(Response.objects.count(), 0)
