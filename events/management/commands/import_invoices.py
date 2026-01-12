import csv
from argparse import ArgumentParser

from django.core.management.base import BaseCommand, no_translations
from django.conf import settings

from djmoney.money import Money

from events.models.events import Event
from events.models.orgs import EventOrg, EventOrgInvoice
from events.models.orgs import get_invoice_upload_dir


class Command(BaseCommand):
    event: Event
    help = (
        "Bulk import invoices for the specified event organization. "
        "You must place invoices in the private storage, under the "
        "default upload path (private/invoices/{event.slug}/"
    )

    def add_arguments(self, parser: ArgumentParser):
        # Lots of required --flags is not very "CLI convention-compliant",
        # but it sure makes things crystal clear when you are importing
        # hundreds of invoices and mistakes have financial implications.

        parser.add_argument(
            "--filename",
            help="CSV to import data from.",
            required=True,
        )
        parser.add_argument(
            "--csv-delimiter",
            help="CSV field delimiter to use",
            default=";",
        )
        parser.add_argument(
            "--event-slug",
            help="CSV to import data from.",
            required=True,
        )
        parser.add_argument(
            "--invoice-name",
            help="User-friendly, long invoice name.",
            required=True,
        )
        parser.add_argument(
            "--invoice-tag",
            help="Machine-friendly, short invoice slug tag for automation.",
            default="",
        )
        parser.add_argument(
            "--invoice-currency",
            help="Currency to use for all invoices.",
            default=settings.CURRENCY,
        )
        parser.add_argument(
            "--invoice-filename-template",
            help="Template for a file path set on the invoice.file attribute, will be formatted with CSV row contents.",
            default="{document_id}.pdf",
        )
        parser.add_argument(
            "--default-notes",
            help="Notes to set on all created objects.",
            default="",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Just try to parse and prepare invoices, do not save them to the database yet.",
        )

    def generate_invoice(
        self, event: Event, orgs: dict[str, EventOrg], row: dict[str, str | int | float], args: dict[str, str]
    ) -> EventOrgInvoice:
        try:
            org = orgs[row["org_id"]]
        except KeyError as e:
            raise ValueError(f"Cannot find EventOrg by ID: {row}") from e

        invoice = EventOrgInvoice(
            event=event,
            event_org=org,
            name=args["invoice_name"],
            tag=args["invoice_tag"],
            document_id=row["document_id"],
            file="",
            net_value=Money(row["net_value"], currency=args["invoice_currency"]),
            tax_value=Money(row["tax_value"], currency=args["invoice_currency"]),
            gross_value=Money(row["gross_value"], currency=args["invoice_currency"]),
            notes=args["default_notes"],
        )

        invoice_filename = args["invoice_filename_template"].format(**row)
        invoice.file = get_invoice_upload_dir(invoice, invoice_filename)

        return invoice

    @no_translations
    def handle(self, **options):
        slug = options["event_slug"]
        try:
            event = Event.objects.get(slug=slug)
            self.stderr.write(f"Found event: {event}")
        except Event.DoesNotExist as e:
            raise ValueError(f"Requested event '{slug}' not found, bailing out!") from e

        orgs: dict[str, EventOrg] = {str(o.id): o for o in event.eventorg_set.all()}

        invoices: list[EventOrgInvoice] = []
        with open(options["filename"], newline="") as csvfile:
            invoices = [
                self.generate_invoice(event, orgs, row, options)
                for row in csv.DictReader(csvfile, delimiter=options["csv_delimiter"])
            ]

        if not options["dry_run"]:
            for invoice in invoices:
                invoice.save()
