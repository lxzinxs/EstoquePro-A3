"""Endpoints organizados por área; URLs públicas permanecem iguais."""

from .accounts import member, plans, signup, subscription
from .finance import (
    analysis,
    labels,
    nfe,
    payment,
    report,
    share_order,
    suggested_order,
)
from .jobs import job_file, queue
from .organizations import branding, business, switch
from .records import listing, new_record
from .stock import (
    action,
    barcode,
    batch,
    dashboard,
    movement,
    notifications,
    reorder_level,
    transfer,
)

__all__ = [
    "reorder_level",
    "signup",
    "member",
    "plans",
    "subscription",
    "switch",
    "business",
    "branding",
    "listing",
    "new_record",
    "dashboard",
    "movement",
    "batch",
    "transfer",
    "action",
    "barcode",
    "notifications",
    "payment",
    "nfe",
    "analysis",
    "report",
    "share_order",
    "labels",
    "suggested_order",
    "queue",
    "job_file",
]
