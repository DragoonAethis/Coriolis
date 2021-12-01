from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from .models import User, Event, EventPage, TicketType, ApplicationType, Ticket, Payment, Application

# Ensure users go through the allauth workflow when logging into admin.
admin.site.login = staff_member_required(admin.site.login, login_url='/accounts/login')

# No special handling for these two.
admin.site.register(User)
admin.site.register(Payment)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'ticket_code_length')


@admin.register(EventPage)
class EventPageAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'slug', 'hidden')


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'code_prefix', 'price', 'max_tickets', 'tickets_remaining')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'event', 'status', 'nickname')


@admin.register(ApplicationType)
class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'slug', 'registration_from', 'registration_to')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'event', 'phone', 'email')
