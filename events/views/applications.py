import logging
import datetime
from typing import List, Dict, Optional

from django import forms
from django.forms.widgets import Textarea, TextInput
from django.core.mail import EmailMessage
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import FormView
from django.conf import settings

from events.forms import ApplicationForm
from events.models import Event, ApplicationType, Application


class ApplicationView(FormView):
    event: Event
    type: ApplicationType
    template_name = 'events/applications/application_form.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs['slug'])
        self.type = get_object_or_404(ApplicationType, event=self.event, id=self.kwargs['id'])

        if not self.validate_application_type():
            return redirect('event_index', self.event.slug)

        return super().dispatch(*args, **kwargs)

    def validate_application_type(self) -> bool:
        """Check whenever the current ticket type can be purchased online."""

        if self.type.event_id != self.event.id:
            messages.error(self.request, _("This application cannot be submitted for this event!"))
            return False

        now = datetime.datetime.now()

        if not self.type.registration_from < now:
            messages.error(self.request, _("This application is not yet open. Come back later."))
            return False

        if not now < self.type.registration_to:
            messages.error(self.request, _("This application submission period has ended."))
            return False

        return True

    def get_dynamic_fields(self, template: str) -> List[Dict[str, Optional[str]]]:
        dynamic_fields = []
        for line in template.splitlines():
            line = line.strip()
            if len(line) == 0 or line.startswith('#'):
                continue

            parts = line.split('|')
            if len(parts) < 2:
                logging.warning(f"Invalid parts definition: {parts}")
                continue

            dynamic_fields.append({
                'key': parts[0],
                'label': parts[1],
                'help_text': None if len(parts) == 2 else parts[2]
            })

        return dynamic_fields

    def get_form(self, form_class=None):
        form = ApplicationForm(event=self.event, type=self.type, **self.get_form_kwargs())
        form.dynamic_fields = self.get_dynamic_fields(self.type.template)

        for field in form.dynamic_fields:
            form.fields[field['key']] = forms.CharField(label=field['label'], required=True,
                                                        help_text=field['help_text'])

        form.fields['notes'] = forms.CharField(label=_("Notes"), required=False, widget=Textarea,
                                               help_text=_("Optional extra notes - add anything you want!"))

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'event': self.event, 'type': self.type})
        return context

    def form_invalid(self, form):
        form.is_valid()
        print('oh no')

    def form_valid(self, form):
        application = Application(user=self.request.user,
                                  event=self.event,
                                  type=self.type,
                                  status=Application.ApplicationStatus.WAITING,
                                  name=form.cleaned_data['name'],
                                  email=form.cleaned_data['email'],
                                  phone=form.cleaned_data['phone'])

        dynamic_answers = [(field['label'], form.cleaned_data[field['key']])
                           for field in form.dynamic_fields]

        dynamic_answers.append((_("Notes"), form.cleaned_data['notes']))
        application.application = "\n".join([f"- {name}: {value}" for name, value in dynamic_answers])

        application.save()

        EmailMessage(
            f"{self.event.name}: {_('Application')} '{application.name}'",
            render_to_string("events/emails/new_application.html", {
                'event': self.event,
                'application': application,
            }),
            settings.SERVER_EMAIL,
            [self.event.org_mail, application.email]
        ).send()

        messages.success(self.request, _("Your application was submitted successfully. Orgs will be in touch soon."))
        return redirect('event_index', self.event.slug)
