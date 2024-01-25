from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import ListView
from django.views.generic.edit import FormView

from events.forms.orgs import BillingDetailsForm
from events.forms.registration import EventOrgTicketRegistrationForm
from events.models import Event, EventOrg, Ticket, TicketStatus, TicketSource
from events.models import EventOrgBillingDetails
from events.tasks.ticket_renderer import render_ticket_variants
from events.utils import generate_ticket_code


def get_event_and_org(view, slug, org_id) -> tuple[Event, EventOrg]:
    event = get_object_or_404(Event, slug=slug)
    org = get_object_or_404(EventOrg, event=event, id=org_id)

    if view.request.user != org.owner or not view.request.user.is_superuser:
        messages.error(view.request, _("You don't have permissions to access this page."))
        return redirect("event_index", view.event.slug)

    return event, org


class BillingDetailsListView(ListView):
    model = EventOrgBillingDetails
    template_name = "events/orgs/billing.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event, self.org = get_event_and_org(self, self.kwargs["slug"], self.kwargs["org_id"])
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return EventOrgBillingDetails.objects.filter(event_org=self.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["org"] = self.org
        return context


class BillingDetailsCreateView(FormView):
    template_name = "events/orgs/billing_add.html"
    form_class = BillingDetailsForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event, self.org = get_event_and_org(self, self.kwargs["slug"], self.kwargs["org_id"])
        return super().dispatch(*args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        form.helper = FormHelper()
        form.helper.form_method = "post"
        form.helper.add_input(Submit("submit", _("Add billing details")))

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["org"] = self.org
        return context

    def form_valid(self, form):
        deets = EventOrgBillingDetails(
            event=self.event,
            event_org=self.org,
            name=form.cleaned_data["name"],
            tax_id=form.cleaned_data["tax_id"],
            address=form.cleaned_data["address"],
            postcode=form.cleaned_data["postcode"],
            city=form.cleaned_data["city"],
            representative=form.cleaned_data["representative"],
        )

        deets.save()
        messages.info(self.request, _("Billing details added."))

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("event_org_billing_details_list", kwargs={"slug": self.event.slug, "org_id": self.org.id})


class EventOrgTicketCreateView(FormView):
    template_name = "events/orgs/tickets_add.html"
    form_class = EventOrgTicketRegistrationForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event, self.org = get_event_and_org(self, self.kwargs["slug"], self.kwargs["org_id"])

        if not self.org.target_ticket_type:
            messages.error(
                self.request, _("Ticket type is not set for this organization - please contact the event organizers.")
            )
            return redirect("event_index", self.event.slug)

        if self.org.ticket_set.count() >= self.org.target_ticket_count:
            messages.error(self.request, _("You have reached the maximum amount of tickets."))
            return redirect("event_index", self.event.slug)

        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event, "org_id": self.org.id})
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        form.helper = FormHelper()
        form.helper.form_method = "post"
        form.helper.add_input(Submit("submit", _("Add ticket")))

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["org"] = self.org
        return context

    def form_valid(self, form):
        ticket = Ticket(
            user=self.request.user,
            event=self.event,
            type=self.org.target_ticket_type,
            org=self.org,
            status=TicketStatus.READY,
            source=TicketSource.ONLINE,
            name=form.cleaned_data["name"],
            email=form.cleaned_data["email"],
            phone=form.cleaned_data["phone"],
            age_gate=form.cleaned_data["age_gate"],
            notes=form.cleaned_data.get("notes"),
        )

        try:
            ticket.code = generate_ticket_code(self.event)
        except ValueError as ex:
            messages.error(self.request, str(ex))
            return redirect("event_index", self.event.slug)

        try:
            ticket.save()
        except Exception as ex:  # noqa
            return redirect("event_index", self.event.slug)

        if ticket.type.can_personalize:
            render_ticket_variants.send(str(ticket.id))

        messages.success(
            self.request,
            _("Thank you for your registration! You can see your ticket details below."),
        )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("event_index", kwargs={"slug": self.event.slug})
