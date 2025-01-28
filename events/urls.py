from django.urls import path

from events.views.applications import ApplicationSubmissionView, application_details
from events.views.crew.accreditation import CrewIndexNewView, CrewExistingTicketView, CrewFindTicketView
from events.views.crew.mod_queue import (
    TicketModQueueListView,
    TicketModQueueDepersonalizeFormView,
    mod_queue_approve_selected,
)
from events.views.crew.orgs import CrewEventOrgListView, CrewEventOrgTicketListView
from events.views.misc import (
    index,
    event_index,
    event_page,
    ticket_picker,
    ticket_details,
    ticket_payment,
    ticket_payment_finalize,
    ticket_post_registration,
)
from events.views.orgs import (
    BillingDetailsListView,
    BillingDetailsCreateView,
    EventOrgTicketCreateView,
)
from events.views.prometheus import prometheus_status
from events.views.registrations import RegistrationView, CancelRegistrationView, UpdateTicketView

# Note: Only the event/<slug:slug>/ path should end with a slash.
# All the others should not, if possible.

urlpatterns = [
    path(
        "event/<slug:slug>/",
        event_index,
        name="event_index",
    ),
    path(
        "event/<slug:slug>/prometheus/<str:key>",
        prometheus_status,
        name="prom_stats",
    ),
    path(
        "event/<slug:slug>/page/<slug:page_slug>",
        event_page,
        name="event_page",
    ),
    path(
        "event/<slug:slug>/ticket/new",
        ticket_picker,
        name="ticket_picker",
    ),
    path(
        "event/<slug:slug>/ticket/new/<int:id>",
        RegistrationView.as_view(),
        name="registration_form",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>",
        ticket_details,
        name="ticket_details",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/thank_you",
        ticket_post_registration,
        name="ticket_post_registration",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/update",
        UpdateTicketView.as_view(),
        name="ticket_update",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/cancel",
        CancelRegistrationView.as_view(),
        name="ticket_cancel",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/pay",
        ticket_payment,
        name="ticket_payment",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/pay/<uuid:payment_id>",
        ticket_payment_finalize,
        name="ticket_payment_finalize",
    ),
    path(
        "event/<slug:slug>/application/new/<int:id>",
        ApplicationSubmissionView.as_view(),
        name="application_form",
    ),
    path(
        "event/<slug:slug>/application/<uuid:app_id>",
        application_details,
        name="application_details",
    ),
    path(
        "event/<slug:slug>/crew",
        CrewIndexNewView.as_view(),
        name="crew_index",
    ),
    path(
        "event/<slug:slug>/crew/search",
        CrewFindTicketView.as_view(),
        name="crew_find_ticket",
    ),
    path(
        "event/<slug:slug>/crew/ticket/<uuid:ticket_id>",
        CrewExistingTicketView.as_view(),
        name="crew_existing_ticket",
    ),
    path(
        "event/<slug:slug>/crew/orgs",
        CrewEventOrgListView.as_view(),
        name="crew_orgs",
    ),
    path(
        "event/<slug:slug>/crew/orgs/<uuid:org_id>/ticket",
        CrewEventOrgTicketListView.as_view(),
        name="crew_orgs_tickets",
    ),
    path(
        "event/<slug:slug>/mod_queue",
        TicketModQueueListView.as_view(),
        name="mod_queue_list",
    ),
    path(
        "event/<slug:slug>/mod_queue/approve",
        mod_queue_approve_selected,
        name="mod_queue_approve",
    ),
    path(
        "event/<slug:slug>/mod_queue/<uuid:ticket_id>/depersonalize",
        TicketModQueueDepersonalizeFormView.as_view(),
        name="mod_queue_depersonalize",
    ),
    path(
        "event/<slug:slug>/org/<uuid:org_id>/ticket/add",
        EventOrgTicketCreateView.as_view(),
        name="event_org_tickets_add",
    ),
    path(
        "event/<slug:slug>/org/<uuid:org_id>/billing_details",
        BillingDetailsListView.as_view(),
        name="event_org_billing_details_list",
    ),
    path(
        "event/<slug:slug>/org/<uuid:org_id>/billing_details/add",
        BillingDetailsCreateView.as_view(),
        name="event_org_billing_details_add",
    ),
    path("", index, name="index"),
]
