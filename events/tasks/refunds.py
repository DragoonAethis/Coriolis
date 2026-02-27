import logging

import dramatiq

from events.models import RefundRequest


@dramatiq.actor
def execute_single_refund(refund_id: str):
    refund = RefundRequest.objects.get(refund_id)
    refund.execute()


@dramatiq.actor
def execute_refunds():
    refunds = RefundRequest.objects.filter(approved=True, executed=None)
    logging.info("Scheduling %d refunds...", refunds.count())

    for refund in refunds:
        execute_single_refund.send(str(refund.id))
