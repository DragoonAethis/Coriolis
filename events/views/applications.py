import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import FormView

from events.dynaforms.utils import get_pretty_answers
from events.forms.applications import ApplicationDynaform
from events.models import Event, ApplicationType, Application, Ticket
from events.templatetags.events import render_markdown


class ApplicationView(FormView):
    event: Event
    type: ApplicationType

    form_class = ApplicationDynaform
    template_name = "events/applications/application_form.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        self.type = get_object_or_404(ApplicationType, event=self.event, id=self.kwargs["id"])

        valid, error_msg = self.validate_application_type()
        if not valid:
            messages.error(self.request, error_msg)
            return redirect("event_index", self.event.slug)

        return super().dispatch(*args, **kwargs)

    def validate_application_type(self) -> tuple[bool, str | None]:
        """Check whenever the current ticket type can be purchased online."""
        if self.type.event_id != self.event.id:
            return False, _("This application cannot be submitted for this event!")

        if (
            self.type.requires_valid_ticket
            and Ticket.objects.filter(event=self.event, user=self.request.user)
            .valid_statuses_only()
            .not_onsite()
            .count()
            < 1
        ):
            return False, _("You must buy a ticket for this event before submitting an application.")

        now = datetime.datetime.now()

        if not self.type.registration_from < now:
            return False, _("This application is not yet open. Come back later.")

        if not now < self.type.registration_to:
            return False, _("This application submission period has ended.")

        return True, None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "event": self.event,
                "application_type": self.type,
                "template": self.type.template,
            }
        )
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"event": self.event, "application_type": self.type})
        return context

    def form_valid(self, form: ApplicationDynaform):
        prefixed_answers = {key: form.cleaned_data[key] for key in form.dynamic_fields.keys()}

        prefix = form.dynaform.get_prefix()
        answers = {key.removeprefix(prefix): data for key, data in prefixed_answers.items()}

        application = Application(
            user=self.request.user,
            event=self.event,
            type=self.type,
            status=Application.ApplicationStatus.WAITING,
            name=form.cleaned_data["name"],
            email=form.cleaned_data["email"],
            phone=form.cleaned_data["phone"],
            notes=form.cleaned_data["notes"],
            answers=answers,
        )

        application.save()

        pretty_answers = {}
        if application.answers:
            pretty_answers = get_pretty_answers(prefixed_answers, form.dynamic_fields)

        EmailMessage(
            subject=_("%(event)s: Application '%(name)s'") % {"event": self.event.name, "name": application.name},
            body=render_to_string(
                "events/emails/new_application.html",
                {
                    "event": self.event,
                    "application": application,
                    "answers": pretty_answers,
                },
            ).strip(),
            to=application.get_notification_emails(),
            reply_to=application.get_notification_emails(),
        ).send()

        if self.type.submission_message:
            notify_msg = render_markdown(self.type.submission_message, strip_wrapper=True)
        else:
            notify_msg = _("Your application was submitted successfully. Orgs will be in touch soon.")

        messages.success(
            self.request,
            notify_msg,
        )
        return redirect("event_index", self.event.slug)
