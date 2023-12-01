from django.urls import path

from . import views

urlpatterns = [
    path("event/<slug:slug>/", views.event_index, name="event_index"),
    path(
        "event/<slug:slug>/prometheus/<str:key>",
        views.prometheus_status,
        name="prom_stats",
    ),
    path("event/<slug:slug>/page/<slug:page_slug>", views.event_page, name="event_page"),
    path("event/<slug:slug>/ticket/new/", views.ticket_picker, name="ticket_picker"),
    path(
        "event/<slug:slug>/ticket/new/<int:id>",
        views.RegistrationView.as_view(),
        name="registration_form",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>",
        views.ticket_details,
        name="ticket_details",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/update",
        views.UpdateTicketView.as_view(),
        name="ticket_update",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/cancel",
        views.CancelRegistrationView.as_view(),
        name="ticket_cancel",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/pay",
        views.ticket_payment,
        name="ticket_payment",
    ),
    path(
        "event/<slug:slug>/ticket/<uuid:ticket_id>/pay/<uuid:payment_id>",
        views.ticket_payment_finalize,
        name="ticket_payment_finalize",
    ),
    path(
        "event/<slug:slug>/application/new/<int:id>",
        views.ApplicationView.as_view(),
        name="application_form",
    ),
    path(
        "event/<slug:slug>/application/<uuid:app_id>",
        views.application_details,
        name="application_details",
    ),
    path("crew/<slug:slug>/", views.CrewIndexNewView.as_view(), name="crew_index"),
    path(
        "crew/<slug:slug>/ticket/",
        views.CrewFindTicketView.as_view(),
        name="crew_find_ticket",
    ),
    path(
        "crew/<slug:slug>/ticket/<uuid:ticket_id>",
        views.CrewExistingTicketView.as_view(),
        name="crew_existing_ticket",
    ),
    path(
        "event/<slug:slug>/mod_queue/",
        views.TicketModQueueListView.as_view(),
        name="mod_queue_list",
    ),
    path(
        "event/<slug:slug>/mod_queue/<uuid:ticket_id>/depersonalize",
        views.TicketModQueueDepersonalizeFormView.as_view(),
        name="mod_queue_depersonalize",
    ),
    path("", views.index, name="index"),
]
