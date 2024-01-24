from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from events.models import TicketType, ApplicationType


class EventContextBasedObjectFilter(admin.SimpleListFilter):
    object_type = None  # Must be an entity to filter on

    def lookups(self, request, model_admin):
        qs = self.object_type.objects.select_related("event")
        if event_id := request.GET.get("event__id__exact"):
            qs = qs.filter(event_id=event_id)

        return [(t.id, str(t)) for t in list(qs)]

    def queryset(self, request, queryset):
        if value := self.value():
            queryset = queryset.filter(type_id=self.value())

        return queryset


class EventContextBasedTicketTypeFilter(EventContextBasedObjectFilter):
    title = _("ticket type")
    parameter_name = "ticket_type"
    object_type = TicketType


class EventContextBasedApplicationTypeFilter(EventContextBasedObjectFilter):
    title = _("application type")
    parameter_name = "application_type"
    object_type = ApplicationType
