import datetime
import os
import uuid
from typing import Literal

import pyrage
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.files.uploadedfile import UploadedFile
from django.http import Http404
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import FormView
from sentry_sdk import capture_exception

from events.dynaforms.answers import ComplexAnswerFileUpload
from events.dynaforms.fields import FileField as DynaFileField
from events.dynaforms.utils import get_pretty_answers
from events.forms.applications import ApplicationDynaform, ApplicationStatusSelfServiceForm
from events.models import Event, ApplicationType, Application, Ticket, AgePublicKey
from events.templatetags.events import render_markdown


def get_event_app_by_id(request, event_slug, app_id, wanted_perm='events.view_application'):
    event = get_object_or_404(Event, slug=event_slug)
    application = get_object_or_404(Application, id=app_id, event=event)

    user_is_submitter = application.user_id == request.user.id
    user_is_elevated = request.user.is_staff and request.user.has_perm(wanted_perm)

    if not user_is_submitter and not user_is_elevated:
        raise Http404(_("You don't own this application!"))

    return event, application


class ApplicationSubmissionView(FormView):
    event: Event
    type: ApplicationType
    key: str | None

    form_class = ApplicationDynaform
    template_name = "events/applications/application_form.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        self.type = get_object_or_404(ApplicationType, event=self.event, id=self.kwargs["id"])
        self.key = self.request.GET.get("key")

        valid, error_msg = self.validate_application_type()
        if not valid:
            messages.error(self.request, error_msg)
            return redirect("event_index", self.event.slug)

        return super().dispatch(*args, **kwargs)

    def validate_application_type(self) -> tuple[bool, str | None]:
        """Check whenever the current ticket type can be purchased online."""
        if self.type.event_id != self.event.id:
            return False, _("This application cannot be submitted for this event!")

        if self.key:
            target_keys = [x.strip() for x in self.type.secret_keys.splitlines()]
            for maybe_key in target_keys:
                if not maybe_key or maybe_key.startswith("#"):
                    continue

                if self.key == maybe_key:
                    # Ignore all requirements and just...
                    return True, None

            # If the key is set but did not match any secret keys, unset it:
            self.key = None

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

    def get_cloned_initial_data(self, application_id: str) -> dict:
        initial = {}
        err_msg = _("The cloned application does not exist, you cannot access it or is not valid for this form.")
        try:
            app = Application.objects.get(id=application_id)
        except Application.DoesNotExist:
            messages.warning(self.request, err_msg)
            return initial

        if app.type_id != self.type.id:
            messages.warning(self.request, err_msg)
            return initial

        user_is_privileged = self.request.user.is_staff and self.request.user.has_perm("event.edit_application")

        if not (user_is_privileged or app.user == self.request.user):
            messages.warning(self.request, err_msg)
            return initial

        # Non-dynamic fields:
        initial["email"] = app.email
        initial["phone"] = app.phone.as_e164
        initial["notes"] = app.notes

        # Dynamic form answers:
        df_prefix = f"df__{ApplicationDynaform.DYNAFORM_NAME}__"
        for key, value in app.answers.items():
            if not value:
                continue

            if isinstance(value, dict):
                continue  # Complex answer types - nope out!

            initial[df_prefix + key] = value

        # fmt: off
        messages.info(self.request, _("The form was prefilled with data based on another application: ") + app.name)
        return initial

    def get_initial(self):
        initial = super().get_initial()

        if self.key:
            initial["key"] = self.key

        if cloned_application_id := self.request.GET.get("clone_application", None):
            initial.update(self.get_cloned_initial_data(cloned_application_id))

        return initial

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

    def form_invalid(self, form):
        messages.error(self.request, _("YOUR APPLICATION WAS *NOT* SUBMITTED - scroll down to see errors."))
        return super().form_invalid(form)

    def form_valid(self, form: ApplicationDynaform):
        prefixed_answers = {key: form.cleaned_data[key] for key in form.dynamic_fields.keys()}

        prefix = form.dynaform.get_prefix()
        answers = {key.removeprefix(prefix): data for key, data in prefixed_answers.items()}

        # Process file uploads
        for upload_name, uploaded_file in answers.items():
            if not isinstance(uploaded_file, UploadedFile):
                continue

            field_config: DynaFileField = form.dynaform.fields[upload_name]
            uploaded_file: UploadedFile

            _name, extension = os.path.splitext(uploaded_file.name)
            extension = extension.strip().strip(".").lower()
            if not (len(extension) > 0 and extension.isalnum()):
                extension = "unknown"

            if field_config.encrypt:
                recipients, errors = AgePublicKey.resolve_pubkeys(self.event, field_config.pubkeys)
                for key, exc in errors.items():
                    if isinstance(exc, AgePublicKey.DoesNotExist):
                        messages.error(
                            self.request, _("Public key '%s' required for encryption was not found.") % (key,)
                        )
                    else:
                        # Something went wrong, let Sentry handle this quietly until it happens...
                        capture_exception(exc)

                if not recipients:
                    messages.error(
                        self.request, _("Form template invalid: No public keys found for '%s'.") % (upload_name,)
                    )

                # TODO: Stream the output to a temporary file on disk, not ContentFile.
                # While we limit the file upload size anyways, this has potential to break things...
                encrypted_file = ContentFile(b"")
                pyrage.encrypt_io(uploaded_file.file, encrypted_file, recipients=recipients)

                extension = f"{extension}.age"
                file_to_save = encrypted_file
            else:
                file_to_save = uploaded_file.file

            filename = f"{self.event.slug}/{field_config.upload_prefix or upload_name}/{uuid.uuid4()}.{extension}"
            real_filename = storages["private"].save(filename, file_to_save)

            answers[upload_name] = ComplexAnswerFileUpload(
                filename=real_filename,
                encrypted=field_config.encrypt,
            ).model_dump()
            prefixed_answers[f"{prefix}{upload_name}"] = answers[upload_name]

        form_notes = form.cleaned_data["notes"]
        if self.key:
            form_notes = _("[SYSTEM] Form submitted with key:") + f" {self.key}\n" + form_notes

        application = Application(
            user=self.request.user,
            event=self.event,
            type=self.type,
            status=Application.ApplicationStatus.WAITING,
            name=form.cleaned_data["name"],
            email=form.cleaned_data["email"],
            phone=form.cleaned_data["phone"],
            notes=form_notes,
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


class ApplicationStatusSelfServiceView(FormView):
    flow: str
    event: Event
    application: Application

    form_class = ApplicationStatusSelfServiceForm
    template_name = "events/applications/application_self_service_status.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        self.flow = kwargs["flow"]
        if self.flow not in ("approve", "reject"):
            raise Http404("No such application self-service flow, try again?")

        self.event, self.application = get_event_app_by_id(
            request,
            kwargs["slug"],
            kwargs["app_id"],
            'events.change_application'
        )

        if not self.application.can_handle_self_service_status_change():
            raise Http404(_("Applications of this type/status do not allow applicants to change the status by themselves."))

        return super().dispatch(request, *args, **kwargs)

    def get_supercontext(self):
        return {
            "event": self.event,
            "application": self.application,
            "flow": self.flow,
        }

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | self.get_supercontext()

    def get_form_kwargs(self):
        return super().get_form_kwargs() | self.get_supercontext()

    def form_valid(self, form):
        if self.flow == "approve":
            self.application.status = Application.ApplicationStatus.APPROVED
            messages.info(self.request, _("Application approved."))
        elif self.flow == "reject":
            self.application.status = Application.ApplicationStatus.REJECTED
            messages.warning(self.request, _("Application rejected."))

        self.application.save()
        return redirect("application_details", slug=self.event.slug, app_id=self.application.id)


@login_required
def application_details(request, slug, app_id):
    from events.dynaforms.fields import Dynaform
    from events.dynaforms.utils import get_pretty_answers

    event, application = get_event_app_by_id(request, slug, app_id, 'events.view_application')
    dynaform = Dynaform.build(None, application.type.template)

    pretty_answers = {}
    if application.answers:
        pretty_answers = get_pretty_answers(dict(application.answers), dynaform.get_fields())

    return render(
        request,
        "events/applications/application_details.html",
        {
            "event": event,
            "application": application,
            "answers": pretty_answers,
        },
    )
