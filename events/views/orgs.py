from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic.edit import FormView
from django.views.generic.detail import DetailView
from django.http import FileResponse

from events.forms.orgs import BillingDetailsForm
from events.forms.registration import EventOrgTicketRegistrationForm
from events.models import Event, EventOrg, EventOrgInvoice, Ticket, TicketStatus, TicketSource, EventOrgBillingDetails, User
from events.tasks.ticket_renderer import render_ticket_variants
from events.utils import generate_ticket_code


def get_event_and_org(slug, org_id) -> tuple[Event, EventOrg]:
    event = get_object_or_404(Event, slug=slug)
    org = get_object_or_404(EventOrg, event=event, id=org_id)
    return event, org


def check_org_perms(org: EventOrg, user: User, perms: list[str]):
    """Allows access if the user either owns the org, or has
    event-wide org management permissions."""
    if not user.is_authenticated:
        raise PermissionDenied

    if user != org.owner and not user.has_perms(perms):
        raise PermissionDenied


class EventOrgInvoicingOverview(DetailView):
    model = EventOrg
    template_name = "events/orgs/billing.html"

    event: Event
    org: EventOrg

    def dispatch(self, *args, **kwargs):
        self.event, self.org = get_event_and_org(self.kwargs["slug"], self.kwargs["org_id"])
        check_org_perms(self.org, self.request.user, ["events.crew_orgs", "events.crew_orgs_view_billing_details"])
        return super().dispatch(*args, **kwargs)

    def get_object(self, queryset=None):
        return self.org

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["org"] = self.org
        context["is_owner"] = self.org.owner == self.request.user
        context["invoices"] = self.org.invoice_set.order_by("created")
        context["billing_details"] = self.org.billing_details_set.order_by("name")
        return context


def download_invoice(request, slug, org_id, invoice_id):
    event, org = get_event_and_org(slug, org_id)
    check_org_perms(org, request.user, [
        "events.crew_orgs",
        "events.crew_orgs_view_invoices",
        "events.crew_orgs_view_billing_details",
    ])

    invoice: EventOrgInvoice = get_object_or_404(EventOrgInvoice, event=event, id=invoice_id)

    return FileResponse(
        invoice.file.open("rb"),
        as_attachment=True,
        filename=invoice.file.name,
        headers={"Content-Type": "application/octet-stream"},
    )


class BillingDetailsCreateView(FormView):
    template_name = "events/orgs/billing_add.html"
    form_class = BillingDetailsForm

    event: Event
    org: EventOrg

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event, self.org = get_event_and_org(self.kwargs["slug"], self.kwargs["org_id"])
        check_org_perms(self.org, self.request.user, ["events.crew_orgs", "events.crew_orgs_view_billing_details"])
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
        return reverse_lazy("event_org_invoices_overview", kwargs={"slug": self.event.slug, "org_id": self.org.id})


class EventOrgTicketCreateView(FormView):
    template_name = "events/orgs/tickets_add.html"
    form_class = EventOrgTicketRegistrationForm

    event: Event
    org: EventOrg

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event, self.org = get_event_and_org(self.kwargs["slug"], self.kwargs["org_id"])
        check_org_perms(self.org, self.request.user, ["events.crew_orgs", "events.crew_accreditation"])

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
