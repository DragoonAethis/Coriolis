import datetime
import decimal
import io
from pprint import pformat

import xlsxwriter
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.forms import CheckboxSelectMultiple
from django.forms import ModelForm
from django.http import FileResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from events.models import (
    User,
    Event,
    EventPage,
    TicketRenderer,
    NotificationChannel,
    TicketFlag,
    TicketType,
    Ticket,
    Payment,
    Application,
    ApplicationType,
)

# Ensure users go through the allauth workflow when logging into admin.
admin.site.login = staff_member_required(admin.site.login, login_url="/accounts/login")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "last_login",
        "date_joined",
        "is_staff",
        "is_superuser",
        "exempt_from_2fa",
    )
    list_filter = ("is_staff", "exempt_from_2fa")
    search_fields = ("email",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "ticket_code_length")
    list_filter = ("active",)
    search_fields = ("name",)
    save_as = True


@admin.register(EventPage)
class EventPageAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "slug", "hidden")
    list_filter = ("event", "page_type", "hidden")
    search_fields = ("name", "slug")
    save_as = True


@admin.register(TicketRenderer)
class TicketRendererAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    save_as = True


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "enabled", "source", "target")
    list_filter = ("event", "source", "target")
    search_fields = ("name",)
    save_as = True


@admin.register(TicketFlag)
class TicketFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "description")
    list_filter = ("event",)
    search_fields = ("name",)
    save_as = True


class TicketTypeAdminForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event_id = self.instance.event_id

        if "flags" in self.fields:
            qs = TicketFlag.objects
            qs = qs.filter(event_id=event_id) if event_id else qs.none()
            self.fields["flags"].queryset = qs


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    form = TicketTypeAdminForm
    list_display = (
        "name",
        "event",
        "code_prefix",
        "price",
        "max_tickets",
        "tickets_remaining",
        "self_registration",
        "on_site_registration",
    )
    list_filter = ("event", "self_registration")
    search_fields = ("name",)
    save_as = True
    formfield_overrides = {
        models.ManyToManyField: {"widget": CheckboxSelectMultiple},
    }


class TicketAdminForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event_id = self.instance.event_id

        if "type" in self.fields and event_id:
            self.fields["type"].queryset = TicketType.objects.filter(event_id=event_id)

        if "flags" in self.fields:
            qs = TicketFlag.objects
            qs = qs.filter(event_id=event_id) if event_id else qs.none()
            self.fields["flags"].queryset = qs


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    form = TicketAdminForm
    readonly_fields = ("created", "updated")
    list_display = (
        "__str__",
        "event",
        "type_link",
        "status",
        "email",
        "nickname",
        "created",
    )
    list_filter = ("event", "type", "status", "source", "created")
    search_fields = ("code", "name", "email", "phone", "nickname")
    formfield_overrides = {
        models.ManyToManyField: {"widget": CheckboxSelectMultiple},
    }

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))

        if obj is not None:
            # Put the read-only event after the user again:
            fields.insert(fields.index("user") + 1, fields.pop(fields.index("event")))

        return fields

    def get_readonly_fields(self, request, obj=None):
        fields = ["created", "updated"]

        if obj is not None:
            # Prevent ticket reassignment across events:
            fields.append("event")

        return fields

    @admin.display(description=_("type"))
    def type_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            mark_safe(reverse("admin:events_tickettype_change", args=(obj.type_id,))),  # noqa: S308
            obj.type.name,
        )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction_id", "total", "status", "event", "ticket_link")
    list_filter = ("event", "status")

    @admin.display(description=_("ticket"))
    def ticket_link(self, obj):
        return format_html(
            '<a href="{}">{}: {}</a>',
            mark_safe(reverse("admin:events_ticket_change", args=(obj.ticket.id,))),  # noqa: S308
            obj.ticket.get_code(),
            obj.ticket.name,
        )


class ApplicationTypeAdminForm(ModelForm):
    def clean_org_emails(self):
        from events.utils import validate_multiple_emails

        mails = self.cleaned_data["org_emails"]
        validate_multiple_emails(mails)
        return mails


@admin.register(ApplicationType)
class ApplicationTypeAdmin(admin.ModelAdmin):
    form = ApplicationTypeAdminForm
    list_display = ("name", "event", "slug", "registration_from", "registration_to")
    list_filter = ("event",)
    search_fields = ("name",)
    save_as = True


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "type_link", "status", "phone", "email", "created")
    list_filter = ("event", "type", "status")
    search_fields = ("name", "email", "phone")
    actions = ("download_as_xlsx",)

    XLSX_SAFE_TYPES = (
        bool,
        str,
        int,
        float,
        decimal.Decimal,
        datetime.date,
        datetime.time,
        datetime.datetime,
        datetime.timedelta,
    )

    @admin.display(description=_("type"))
    def type_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            mark_safe(reverse("admin:events_applicationtype_change", args=(obj.type_id,))),  # noqa: S308
            obj.type.name,
        )

    @admin.action(description=_("Download selected applications as XLSX"))
    def download_as_xlsx(self, request, queryset):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            buffer,
            {
                "in_memory": True,
                "strings_to_urls": False,
            },
        )
        ws = workbook.add_worksheet()

        attr_cols = [
            (_("ID"), lambda a: str(a.id)),
            (_("User"), lambda a: a.user.email),
            (_("Event"), lambda a: a.event.name),
            (_("Type"), lambda a: a.type.name),
            (_("Status"), lambda a: a.get_status_display()),
            (_("Name"), lambda a: a.name),
            (_("Phone"), lambda a: str(a.phone)),
            (_("Email"), lambda a: a.email),
            (_("Notes"), lambda a: a.notes),
            (_("Org Notes"), lambda a: a.org_notes),
        ]

        cur_row = 1  # 0 is for headers
        col_shift = len(attr_cols)
        found_cols = []

        app: Application
        for app in queryset:
            # Common data:
            for col, (_unused_label, expr) in enumerate(attr_cols):
                ws.write(cur_row, col, self.xlsx_safe_value(expr(app)))

            # Application data:
            for key, value in app.answers.items():
                try:
                    col = col_shift + found_cols.index(key)
                except ValueError:
                    found_cols.append(key)
                    col = col_shift + len(found_cols) - 1

                try:
                    error = ws.write(cur_row, col, self.xlsx_safe_value(value))
                    if error:
                        ws.write(cur_row, col, f"ERROR: {error}")
                except:  # noqa
                    ws.write(cur_row, col, "UNKNOWN ERROR!")

            cur_row += 1

        # Headers:
        for col, (label, _unused_expr) in enumerate(attr_cols):
            ws.write(0, col, str(label))

        for col, label in enumerate(found_cols):
            ws.write(0, col + col_shift, label)

        workbook.close()
        buffer.seek(0)

        return FileResponse(
            buffer,
            as_attachment=True,
            filename="export.xlsx",
            headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        )

    @staticmethod
    def xlsx_safe_value(value):
        if type(value) in ApplicationAdmin.XLSX_SAFE_TYPES:
            return value

        return pformat(value)
