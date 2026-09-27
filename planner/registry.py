"""One place describing each editable thing, so a single set of generic views
can handle inline editing, quick-add and delete for all of them."""

from dataclasses import dataclass, field

from . import models as m


@dataclass
class Kind:
    model: type
    label: str  # singular, human
    quick_fields: list  # shown in the "+ Add" form
    drawer_fields: list  # shown in the edit drawer
    icon: str = ""
    list_url: str = ""
    detail_page: bool = False  # has its own page (venues/suppliers) rather than a drawer
    defaults: dict = field(default_factory=dict)


KINDS = {
    "task": Kind(
        m.Task, "task", ["title", "category", "owner", "priority", "due_date"],
        ["title", "status", "category", "owner", "priority", "due_date", "notes"],
        icon="✅", list_url="tasks",
    ),
    "venue": Kind(
        m.Venue, "venue", ["name", "role", "location", "venue_type", "website"],
        [],  # venues have a full page
        icon="🏠", list_url="venues", detail_page=True,
    ),
    "supplier": Kind(
        m.Supplier, "supplier", ["name", "category", "website", "quote_estimate"],
        [],
        icon="📞", list_url="suppliers", detail_page=True,
    ),
    "enquiry": Kind(
        m.Enquiry, "enquiry entry", ["venue", "supplier", "date", "kind", "content"],
        ["date", "kind", "content"],
        icon="💌", list_url="enquiries",
    ),
    "budgetitem": Kind(
        m.BudgetItem, "expense", ["category", "item", "estimate", "quote", "booked_cost"],
        ["item", "category", "status", "estimate", "quote", "booked_cost", "deposit", "paid", "payment_due", "notes"],
        icon="💷", list_url="budget",
    ),
    "budgetcategory": Kind(
        m.BudgetCategory, "budget category", ["name", "icon", "alloc_low", "alloc_medium", "alloc_high"],
        ["name", "icon", "alloc_low", "alloc_medium", "alloc_high"],
        list_url="budget",
    ),
    "guest": Kind(
        m.Guest, "guest", ["name", "side", "group", "relationship", "from_canada"],
        ["name", "side", "group", "relationship", "rsvp", "ceremony", "reception", "evening", "plus_one",
         "children", "dietary", "from_canada", "accommodation", "transport", "notes"],
        icon="👥", list_url="guests",
    ),
    "idea": Kind(
        m.Idea, "idea", ["title", "category", "note", "link", "tags"],
        ["title", "category", "note", "link", "tags"],
        icon="🌿", list_url="ideas",
    ),
    "travel": Kind(
        m.TravelOption, "travel option", ["name", "kind", "area", "price", "link"],
        ["name", "kind", "area", "status", "price", "distance", "rooms", "link", "for_guests", "notes"],
        icon="✈️", list_url="travel",
    ),
    "timeline": Kind(
        m.TimelineItem, "milestone", ["title", "phase"], ["title", "phase", "done"], list_url="timeline",
    ),
    "decision": Kind(
        m.Decision, "decision", ["decision", "answer", "status"],
        ["decision", "answer", "status", "decided_on", "notes"],
        list_url="decisions",
    ),
    "note": Kind(m.Note, "note", ["kind", "text"], ["text", "kind"], list_url="notes"),
    "settings": Kind(
        m.WeddingSettings, "settings", [],
        ["wedding_date", "date_confirmed", "ceremony_venue", "reception_venue", "guest_estimate",
         "target_low", "target_medium", "target_high"],
    ),
}


def kind_for(obj):
    for slug, kind in KINDS.items():
        if isinstance(obj, kind.model):
            return slug, kind
    raise KeyError(type(obj))
