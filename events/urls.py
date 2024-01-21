from django.urls import path

from events.views.applications import ApplicationView
from events.views.crew import CrewIndexNewView, CrewExistingTicketView, CrewFindTicketView
from events.views.misc import index, event_index, event_page, application_details
from events.views.misc import ticket_picker, ticket_details, ticket_payment, ticket_payment_finalize
from events.views.mod_queue import TicketModQueueListView, TicketModQueueDepersonalizeFormView
from events.views.prometheus import prometheus_status
from events.views.registrations import RegistrationView, CancelRegistrationView, UpdateTicketView

urlpatterns = [
    path("event/<slug:slug>/", event_index, name="event_index"),
    path(
        "event/<slug:slug>/prometheus/<str:key>",
        prometheus_status,
        name="prom_stats",
    ),
    path("event/<slug:slug>/page/<slug:page_slug>", event_page, name="event_page"),
    path("event/<slug:slug>/ticket/new/", ticket_picker, name="ticket_picker"),
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
        ApplicationView.as_view(),
        name="application_form",
    ),
    path(
        "event/<slug:slug>/application/<uuid:app_id>",
        application_details,
        name="application_details",
    ),
    path("crew/<slug:slug>/", CrewIndexNewView.as_view(), name="crew_index"),
    path(
        "crew/<slug:slug>/ticket/",
        CrewFindTicketView.as_view(),
        name="crew_find_ticket",
    ),
    path(
        "crew/<slug:slug>/ticket/<uuid:ticket_id>",
        CrewExistingTicketView.as_view(),
        name="crew_existing_ticket",
    ),
    path(
        "event/<slug:slug>/mod_queue/",
        TicketModQueueListView.as_view(),
        name="mod_queue_list",
    ),
    path(
        "event/<slug:slug>/mod_queue/<uuid:ticket_id>/depersonalize",
        TicketModQueueDepersonalizeFormView.as_view(),
        name="mod_queue_depersonalize",
    ),
    path("", index, name="index"),
]
