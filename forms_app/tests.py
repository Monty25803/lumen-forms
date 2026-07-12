from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Answer, Form, Option, Question, Response


class FormWorkflowTests(TestCase):
    def setUp(self):
        self.form = Form.objects.create(
            title="Customer feedback",
            description="Tell us what you think.",
        )
        self.name_question = Question.objects.create(
            form=self.form,
            text="Your name",
            question_type="text",
            order=1,
        )
        self.rating_question = Question.objects.create(
            form=self.form,
            text="How was your experience?",
            question_type="radio",
            order=2,
        )
        self.good_option = Option.objects.create(
            question=self.rating_question,
            text="Good",
            order=1,
        )
        self.bad_option = Option.objects.create(
            question=self.rating_question,
            text="Bad",
            order=2,
        )

    def test_public_user_can_submit_form(self):
        response = self.client.post(
            reverse("form_detail", args=[self.form.id]),
            {
                "question_{}".format(self.name_question.id): "Alex",
                "question_{}".format(self.rating_question.id): str(self.good_option.id),
            },
        )

        self.assertRedirects(response, reverse("form_thanks", args=[self.form.id]))
        stored_response = Response.objects.get(form=self.form)
        text_answer = Answer.objects.get(
            response=stored_response,
            question=self.name_question,
        )
        choice_answer = Answer.objects.get(
            response=stored_response,
            question=self.rating_question,
        )
        self.assertEqual(text_answer.text_answer, "Alex")
        self.assertEqual(list(choice_answer.selected_options.all()), [self.good_option])

    def test_home_hides_response_link_from_public_users(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Fill out form")
        self.assertNotContains(response, reverse("form_responses", args=[self.form.id]))

    def test_response_view_requires_staff_user(self):
        response = self.client.get(reverse("form_responses", args=[self.form.id]))

        self.assertRedirects(
            response,
            "{}?next={}".format(
                reverse("admin:login"),
                reverse("form_responses", args=[self.form.id]),
            ),
        )

    def test_staff_user_can_view_response_link_and_results(self):
        staff_user = get_user_model().objects.create_user(
            username="staff",
            password="password",
            is_staff=True,
        )
        Response.objects.create(form=self.form)

        self.client.force_login(staff_user)
        home_response = self.client.get(reverse("home"))
        responses_response = self.client.get(reverse("form_responses", args=[self.form.id]))

        self.assertContains(home_response, reverse("form_responses", args=[self.form.id]))
        self.assertContains(responses_response, "Customer feedback")
        self.assertContains(responses_response, "1 response(s)")
