import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

# ---------------------------------------------------------------------------
# Shared choices
# ---------------------------------------------------------------------------

OWNER_CHOICES = [("Richard", "Richard"), ("Denver", "Denver"), ("Both", "Both")]
PRIORITY_CHOICES = [("High", "High"), ("Medium", "Medium"), ("Low", "Low")]
PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def choices(*values):
    return [(v, v) for v in values]


ENQUIRY_STATUSES = choices(
    "Idea",
    "To Contact",
    "Enquiry Sent",
    "Awaiting Reply",
    "Replied",
    "Viewing Booked",
    "Shortlisted",
    "Rejected",
    "Booked",
)
AVAILABILITY = choices("Unknown", "Asked", "Available", "Provisional hold", "Unavailable", "Confirmed")
YES_NO = choices("Unknown", "Yes", "No", "Partly")


class Tracked(models.Model):
    """Adds who/when bookkeeping to every record so we can see who touched what."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False
    )

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Wedding-wide settings (singleton)
# ---------------------------------------------------------------------------

SCENARIOS = [("low", "Low"), ("medium", "Medium"), ("high", "Higher")]


class WeddingSettings(Tracked):
    wedding_date = models.DateField(default=datetime.date(2027, 5, 29))
    date_confirmed = models.BooleanField(default=False, help_text="Tick once the venue has confirmed the date.")
    scenario = models.CharField(max_length=10, choices=SCENARIOS, default="medium")
    target_low = models.DecimalField("Low target", max_digits=9, decimal_places=2, default=Decimal("3000"))
    target_medium = models.DecimalField("Medium target", max_digits=9, decimal_places=2, default=Decimal("5000"))
    target_high = models.DecimalField("Higher target", max_digits=9, decimal_places=2, default=Decimal("8000"))
    ceremony_venue = models.ForeignKey(
        "Venue", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", limit_choices_to={"role__in": ["Ceremony", "Both"]}
    )
    reception_venue = models.ForeignKey(
        "Venue", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", limit_choices_to={"role__in": ["Reception", "Both"]}
    )
    guest_estimate = models.PositiveIntegerField("Rough guest estimate", null=True, blank=True)

    class Meta:
        verbose_name_plural = "wedding settings"

    def __str__(self):
        return "Wedding settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def target(self):
        return getattr(self, f"target_{self.scenario}")

    @property
    def days_to_go(self):
        return (self.wedding_date - timezone.localdate()).days


# ---------------------------------------------------------------------------
# Tasks & timeline
# ---------------------------------------------------------------------------

TASK_CATEGORIES = choices(
    "Ceremony", "Venue", "Guests", "Suppliers", "Budget", "Food & Drink", "Music", "Photography",
    "Flowers & Decor", "Clothing", "Travel", "Admin", "Other",
)
TASK_STATUSES = choices(
    "Not Started", "Researching", "Waiting for Reply", "In Progress", "Booked", "Completed", "Not Going Ahead"
)
DONE_STATUSES = ("Completed", "Booked")
CLOSED_STATUSES = ("Completed", "Booked", "Not Going Ahead")


class Task(Tracked):
    title = models.CharField("Task", max_length=200)
    category = models.CharField(max_length=40, choices=TASK_CATEGORIES, default="Other")
    owner = models.CharField(max_length=10, choices=OWNER_CHOICES, default="Both")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="Medium")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=TASK_STATUSES, default="Not Started")
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status in DONE_STATUSES and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status not in DONE_STATUSES:
            self.completed_at = None
        super().save(*args, **kwargs)

    @property
    def is_done(self):
        return self.status in DONE_STATUSES

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status not in CLOSED_STATUSES)


# Planning phases, each with the date it starts. "You are here" is the latest
# phase that has started.
TIMELINE_PHASES = [
    ("now", "Now", datetime.date(2026, 9, 1)),
    ("autumn26", "Autumn 2026", datetime.date(2026, 10, 15)),
    ("winter26", "Winter 2026/27", datetime.date(2026, 12, 1)),
    ("early27", "Early 2027", datetime.date(2027, 2, 1)),
    ("spring27", "Spring 2027", datetime.date(2027, 4, 1)),
    ("may27", "May 2027", datetime.date(2027, 5, 1)),
]


class TimelineItem(Tracked):
    phase = models.CharField(max_length=20, choices=[(k, label) for k, label, _ in TIMELINE_PHASES])
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Venues, suppliers and the enquiry log
# ---------------------------------------------------------------------------

VENUE_ROLES = choices("Ceremony", "Reception", "Both")
VENUE_TYPES = choices(
    "Outdoor / woodland", "Arts centre", "Village hall", "Community hall", "Barn", "Hotel", "Restaurant", "Other"
)


class Venue(Tracked):
    name = models.CharField(max_length=200)
    role = models.CharField("Used for", max_length=20, choices=VENUE_ROLES, default="Reception")
    location = models.CharField(max_length=200, blank=True)
    venue_type = models.CharField("Type", max_length=40, choices=VENUE_TYPES, default="Other")
    website = models.URLField(blank=True)
    contact = models.TextField("Contact details", blank=True)
    distance_from_perth = models.CharField(max_length=60, blank=True, help_text="Approximate unless checked")
    distance_from_ceremony = models.CharField(max_length=60, blank=True)
    capacity = models.CharField(max_length=60, blank=True)
    availability = models.CharField("Our date available?", max_length=30, choices=AVAILABILITY, default="Unknown")
    price_estimate = models.DecimalField("Estimated price £", max_digits=9, decimal_places=2, null=True, blank=True)
    price_quote = models.DecimalField("Confirmed quote £", max_digits=9, decimal_places=2, null=True, blank=True)
    byob = models.CharField("BYOB allowed?", max_length=10, choices=YES_NO, default="Unknown")
    catering = models.TextField("Catering rules / restrictions", blank=True)
    closing_time = models.CharField(max_length=60, blank=True)
    accommodation = models.CharField("Accommodation?", max_length=10, choices=YES_NO, default="Unknown")
    outdoor_space = models.CharField("Outdoor space?", max_length=10, choices=YES_NO, default="Unknown")
    rain_backup = models.CharField("Rain backup?", max_length=10, choices=YES_NO, default="Unknown")
    status = models.CharField(max_length=30, choices=ENQUIRY_STATUSES, default="Idea")
    next_follow_up = models.DateField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField("Our rating", default=0, choices=[(i, "♥" * i or "–") for i in range(6)])
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("venue_detail", args=[self.pk])

    @property
    def follow_up_due(self):
        return bool(self.next_follow_up and self.next_follow_up <= timezone.localdate() and self.status not in ("Rejected", "Booked"))


SUPPLIER_CATEGORIES = choices(
    "Photographer", "Caterer", "Florist", "Cake", "DJ", "Ceilidh band", "Transport", "Hair", "Makeup",
    "Clothing", "Decorations", "Accommodation", "Celebrant", "Other",
)


class Supplier(Tracked):
    name = models.CharField("Company / name", max_length=200)
    category = models.CharField(max_length=40, choices=SUPPLIER_CATEGORIES, default="Other")
    contact = models.TextField(blank=True)
    website = models.URLField(blank=True)
    quote_estimate = models.DecimalField("Estimated price £", max_digits=9, decimal_places=2, null=True, blank=True)
    quote = models.DecimalField("Confirmed quote £", max_digits=9, decimal_places=2, null=True, blank=True)
    status = models.CharField("Enquiry status", max_length=30, choices=ENQUIRY_STATUSES, default="Idea")
    availability = models.CharField(max_length=30, choices=AVAILABILITY, default="Unknown")
    rating = models.PositiveSmallIntegerField("Our rating", default=0, choices=[(i, "♥" * i or "–") for i in range(6)])
    booked = models.BooleanField(default=False)
    next_follow_up = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["category", "created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("supplier_detail", args=[self.pk])

    @property
    def follow_up_due(self):
        return bool(self.next_follow_up and self.next_follow_up <= timezone.localdate() and self.status not in ("Rejected", "Booked"))


ENQUIRY_KINDS = choices(
    "Enquiry prepared", "Enquiry sent", "Reply received", "Phone call", "Viewing", "Quote received",
    "Follow-up sent", "Booked", "Note",
)


class Enquiry(Tracked):
    """One entry in a venue's or supplier's history — paste emails straight in."""

    venue = models.ForeignKey(Venue, null=True, blank=True, on_delete=models.CASCADE, related_name="enquiries")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.CASCADE, related_name="enquiries")
    date = models.DateField(default=timezone.localdate)
    kind = models.CharField("What happened", max_length=30, choices=ENQUIRY_KINDS, default="Note")
    content = models.TextField("Details / pasted email", blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.kind} — {self.subject}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.venue_id and not self.supplier_id:
            raise ValidationError("Pick the venue or supplier this is about.")

    @property
    def subject(self):
        return self.venue or self.supplier


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

BUDGET_STATUSES = choices("Estimate", "Quoted", "Booked", "Deposit paid", "Paid in full", "Not needed")


class BudgetCategory(Tracked):
    name = models.CharField(max_length=60)
    icon = models.CharField(max_length=8, blank=True)
    order = models.PositiveIntegerField(default=0)
    alloc_low = models.DecimalField("Low £", max_digits=9, decimal_places=2, default=0)
    alloc_medium = models.DecimalField("Medium £", max_digits=9, decimal_places=2, default=0)
    alloc_high = models.DecimalField("Higher £", max_digits=9, decimal_places=2, default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "budget categories"

    def __str__(self):
        return self.name

    def allocation(self, scenario):
        return getattr(self, f"alloc_{scenario}")


class BudgetItem(Tracked):
    category = models.ForeignKey(BudgetCategory, on_delete=models.PROTECT, related_name="items")
    item = models.CharField("Supplier / item", max_length=200)
    estimate = models.DecimalField("Estimate £", max_digits=9, decimal_places=2, null=True, blank=True)
    quote = models.DecimalField("Quote £", max_digits=9, decimal_places=2, null=True, blank=True)
    booked_cost = models.DecimalField("Booked cost £", max_digits=9, decimal_places=2, null=True, blank=True)
    deposit = models.DecimalField("Deposit £", max_digits=9, decimal_places=2, null=True, blank=True)
    paid = models.DecimalField("Paid so far £", max_digits=9, decimal_places=2, null=True, blank=True)
    payment_due = models.DateField("Payment due", null=True, blank=True)
    status = models.CharField(max_length=20, choices=BUDGET_STATUSES, default="Estimate")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["category__order", "created_at"]

    def __str__(self):
        return self.item

    @property
    def excluded(self):
        return self.status == "Not needed"

    @property
    def forecast(self):
        """Best current guess at what this will cost: booked > quote > estimate."""
        if self.excluded:
            return Decimal(0)
        for v in (self.booked_cost, self.quote, self.estimate):
            if v is not None:
                return v
        return Decimal(0)

    @property
    def committed(self):
        return Decimal(0) if self.excluded else (self.booked_cost or Decimal(0))

    @property
    def remaining(self):
        """Still to pay on something we've booked."""
        return max(self.committed - (self.paid or 0), Decimal(0))

    @property
    def certainty(self):
        if self.booked_cost is not None:
            return "Booked"
        if self.quote is not None:
            return "Quoted"
        return "Estimate"


# ---------------------------------------------------------------------------
# Guests
# ---------------------------------------------------------------------------

GUEST_SIDES = choices("Richard", "Denver", "Both")
RSVP_CHOICES = choices("Not invited yet", "Invited", "Confirmed", "Declined", "Maybe")


class Guest(Tracked):
    name = models.CharField(max_length=200)
    side = models.CharField("Side", max_length=10, choices=GUEST_SIDES, default="Both")
    group = models.CharField("Family / group", max_length=100, blank=True)
    relationship = models.CharField(max_length=100, blank=True)
    ceremony = models.BooleanField(default=True)
    reception = models.BooleanField(default=True)
    evening = models.BooleanField(default=True)
    rsvp = models.CharField("RSVP", max_length=20, choices=RSVP_CHOICES, default="Not invited yet")
    dietary = models.CharField("Dietary requirements", max_length=200, blank=True)
    plus_one = models.BooleanField("Plus one", default=False)
    children = models.PositiveSmallIntegerField(default=0)
    accommodation = models.BooleanField("Needs accommodation", default=False)
    from_canada = models.BooleanField("Travelling from Canada", default=False)
    transport = models.BooleanField("Needs transport", default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["side", "group", "name"]

    def __str__(self):
        return self.name

    @property
    def headcount(self):
        return 1 + int(self.plus_one) + (self.children or 0)


# ---------------------------------------------------------------------------
# Ideas & inspiration
# ---------------------------------------------------------------------------

IDEA_CATEGORIES = choices(
    "Ceremony", "Reception", "Food & Drink", "Flowers", "Decorations", "Photography", "Clothes", "Music",
    "Cake", "Invitations", "Things for Canadian guests", "General ideas",
)


class Image(models.Model):
    """Uploaded pictures live in the database so nothing is lost between deploys."""

    data = models.BinaryField()
    mime = models.CharField(max_length=40, default="image/jpeg")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_absolute_url(self):
        return reverse("image", args=[self.pk])


class Idea(Tracked):
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=40, choices=IDEA_CATEGORIES, default="General ideas")
    note = models.TextField(blank=True)
    link = models.URLField(blank=True)
    image = models.ForeignKey(Image, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated")
    loved_by_richard = models.BooleanField(default=False)
    loved_by_denver = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def hearts(self):
        return int(self.loved_by_richard) + int(self.loved_by_denver)


# ---------------------------------------------------------------------------
# Travel & accommodation
# ---------------------------------------------------------------------------

TRAVEL_KINDS = choices("Hotel", "Airbnb / cottage", "B&B", "Airport", "Train / bus", "Taxi", "Minibus", "Car hire", "Wedding-day transport", "Other")
TRAVEL_AREAS = choices("Dunkeld / Birnam", "Perth", "Wider Perthshire", "Edinburgh", "Glasgow", "Other")
TRAVEL_STATUSES = choices("Idea", "Researching", "Recommended to guests", "Enquired", "Booked", "Ruled out")


class TravelOption(Tracked):
    name = models.CharField(max_length=200)
    kind = models.CharField("Type", max_length=30, choices=TRAVEL_KINDS, default="Hotel")
    area = models.CharField(max_length=30, choices=TRAVEL_AREAS, default="Dunkeld / Birnam")
    price = models.CharField("Approx. price", max_length=100, blank=True)
    distance = models.CharField("Distance to ceremony / reception", max_length=100, blank=True)
    rooms = models.CharField("Rooms / capacity", max_length=60, blank=True)
    link = models.URLField("Booking link", blank=True)
    status = models.CharField(max_length=30, choices=TRAVEL_STATUSES, default="Idea")
    for_guests = models.BooleanField("Recommend to guests", default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["kind", "created_at"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Decisions log and "things we love / avoid / consider"
# ---------------------------------------------------------------------------

DECISION_STATUSES = choices("Open", "Enquiring", "Provisional", "Decided", "Revisit")


class Decision(Tracked):
    decision = models.CharField(max_length=200)
    answer = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=DECISION_STATUSES, default="Open")
    decided_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.decision


NOTE_KINDS = [("love", "Things we love"), ("avoid", "Things to avoid"), ("consider", "Things to consider")]


class Note(Tracked):
    kind = models.CharField(max_length=10, choices=NOTE_KINDS)
    text = models.CharField(max_length=300)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.text
