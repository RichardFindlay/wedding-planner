"""Starter data taken from our planning brief. Only ever loaded into an empty database.

Prices here are *working allowances*, never quotes — they're stored as estimates
so the budget shows them as such until a real quote comes in.
"""

import datetime
from decimal import Decimal as D

from django.db import transaction

from . import models as m

d = datetime.date

BUDGET = [
    # name, icon, low, medium, high
    ("Ceremony", "🌲", 300, 450, 600),
    ("Reception venue", "🏛️", 300, 600, 900),
    ("Catering", "🍽️", 700, 1100, 1600),
    ("Drinks", "🥂", 300, 500, 800),
    ("Photography", "📷", 150, 650, 1100),
    ("Music / ceilidh / DJ", "🎻", 200, 450, 800),
    ("Flowers", "💐", 50, 150, 300),
    ("Decorations", "🕯️", 100, 150, 250),
    ("Cake / dessert", "🍰", 50, 100, 200),
    ("Clothing", "👔", 200, 300, 400),
    ("Rings", "💍", 100, 150, 250),
    ("Transport", "🚌", 0, 100, 300),
    ("Accommodation", "🛏️", 0, 0, 0),
    ("Stationery", "✉️", 20, 50, 80),
    ("Hair / makeup", "💇", 0, 50, 150),
    ("Gifts", "🎁", 30, 50, 100),
    ("Miscellaneous", "🧺", 200, 150, 170),
]

BUDGET_ITEMS = [
    ("Ceremony", "The Hermitage — ceremony fee", None, "Awaiting pricing from our enquiry."),
    ("Ceremony", "Celebrant", 350, "Working allowance — research humanist / independent celebrants."),
    ("Ceremony", "Marriage notice fees", 100, "Statutory fees — check current National Records of Scotland rates."),
    ("Reception venue", "Reception venue hire", 600, "Working allowance — replace with a real Birnam Arts / hall quote."),
    ("Catering", "Informal catering (pizza / BBQ / hog roast)", 1100, "Working allowance."),
    ("Drinks", "Drinks (bought ourselves if BYOB allowed)", 500, "Depends on venue alcohol / corkage rules."),
    ("Photography", "Photographer", 650, "Working allowance."),
    ("Music / ceilidh / DJ", "Ceilidh band or DJ", 450, "Working allowance."),
    ("Clothing", "Outfits", 300, ""),
    ("Rings", "Rings", 150, ""),
]

TASKS = [
    # title, category, owner, priority, due, status, notes
    ("Send the Hermitage enquiry", "Ceremony", "Richard", "High", d(2026, 9, 30), "In Progress",
     "Drafted. Asks about Sat 29 May 2027, alternative end-of-May dates, current pricing and what's included."),
    ("Contact Birnam Arts", "Venue", "Both", "High", d(2026, 10, 4), "Not Started",
     "Ask: 29 May 2027 availability, wedding hire price, catering rules, alcohol / BYOB, capacity, closing time."),
    ("Establish draft guest numbers", "Guests", "Both", "High", d(2026, 10, 11), "Not Started", ""),
    ("Compare reception venues", "Venue", "Both", "High", d(2026, 10, 25), "Not Started",
     "Birnam Arts vs Murthly Village Hall vs other halls around Dunkeld / Birnam / Perth."),
    ("Ask Murthly Village Hall about availability & hire cost", "Venue", "Both", "Medium", d(2026, 10, 11), "Not Started", ""),
    ("Find other village / community halls nearby", "Venue", "Both", "Medium", d(2026, 10, 18), "Researching",
     "Dunkeld, Birnam, Murthly, Perth, wider Perthshire."),
    ("Draft guest list", "Guests", "Both", "Medium", d(2026, 10, 18), "Not Started", ""),
    ("Agree our working budget scenario", "Budget", "Both", "Medium", d(2026, 10, 15), "Not Started",
     "£5k looks like the sweet spot — sanity check against real quotes."),
    ("Give Canadian family a heads-up on the provisional date", "Travel", "Denver", "Medium", d(2026, 10, 31), "Not Started",
     "Make clear it's provisional until the venue confirms."),
    ("Research photographers", "Suppliers", "Both", "Medium", d(2026, 11, 15), "Not Started", ""),
    ("Research celebrants", "Ceremony", "Both", "Medium", d(2026, 11, 30), "Not Started", ""),
    ("Check the legal paperwork for marrying in Scotland", "Admin", "Both", "Medium", d(2026, 12, 1), "Not Started",
     "Marriage notice forms, timings, and any extra documents needed."),
    ("Think through a wet-weather plan for the Hermitage", "Ceremony", "Both", "Low", None, "Not Started", ""),
    ("Look at accommodation around Dunkeld & Birnam for Canadian guests", "Travel", "Both", "Low", d(2027, 1, 15), "Not Started", ""),
]

TIMELINE = {
    "now": ["Confirm ceremony venue", "Shortlist reception venues"],
    "autumn26": ["Book ceremony", "Book reception", "Create initial guest list"],
    "winter26": ["Photographer", "Catering", "Music", "Accommodation"],
    "early27": ["Outfits", "Flowers", "Transport", "Invitations"],
    "spring27": ["Final guest numbers", "Seating", "Supplier confirmations", "Timings for the day"],
    "may27": ["Final payments", "Weather plan", "Pack & prepare decor", "Wedding day! 💍"],
}

DECISIONS = [
    ("Preferred wedding date", "Saturday 29 May 2027 (nearby end-of-May dates possible)", "Provisional", ""),
    ("Preferred ceremony", "The Hermitage, Dunkeld — ideally around Ossian's Hall", "Enquiring", ""),
    ("Overall approach", "Ceremony at the Hermitage → inexpensive function venue nearby", "Decided",
     "Spend on the things that matter rather than a big venue package."),
    ("Reception venue", "", "Open", "Birnam Arts is the strong option; Murthly Village Hall as a lower-cost alternative."),
    ("Guest count", "", "Open", ""),
    ("Budget", "£5k working target (Low £3k / Higher £8k also modelled)", "Provisional", ""),
    ("Style", "Relaxed, natural, Scottish woodland — not a formal traditional wedding", "Decided", ""),
]

NOTES = {
    "love": ["Nature", "Outdoors", "Scenic Perthshire", "Relaxed atmosphere", "Meaningful ceremony", "Good food",
             "Fun evening with friends & family", "Keeping the wedding personal"],
    "avoid": ["Excessive wedding-industry markup", "Overly formal wedding packages", "Paying thousands just for a venue",
              "Unnecessary wedding extras"],
    "consider": ["Scottish weather", "Wet-weather plan", "Guests travelling from Canada", "Transport between venues",
                 "Accommodation", "Venue closing times", "Catering restrictions", "Alcohol / corkage rules", "Accessibility"],
}

IDEAS = [
    ("Woodland ceremony", "Ceremony", "Intimate, relaxed, surrounded by trees.", "woodland, outdoors"),
    ("The Hermitage", "Ceremony", "Ossian's Hall and the waterfall — photos around the Hermitage afterwards.", "hermitage, dunkeld"),
    ("Natural greenery", "Flowers", "", "greenery"),
    ("Wildflowers", "Flowers", "", "wildflowers"),
    ("Fairy lights", "Decorations", "", "lights"),
    ("Candles", "Decorations", "", "lights"),
    ("Long tables", "Reception", "Everyone together, feast-style.", "tables"),
    ("Relaxed dinner", "Food & Drink", "", "food"),
    ("Wood-fired pizza", "Food & Drink", "", "food, pizza"),
    ("BBQ", "Food & Drink", "", "food"),
    ("Hog roast", "Food & Drink", "", "food"),
    ("Ceilidh", "Music", "", "ceilidh, dancing"),
    ("Sunset photographs", "Photography", "", "photos"),
    ("Scottish touches", "General ideas", "Distinctly Perthshire without going full traditional.", "scottish"),
    ("Informal styling", "General ideas", "Informal rather than traditional wedding styling.", "style"),
]

TRAVEL = [
    # name, kind, area, price, distance, notes
    ("Edinburgh Airport", "Airport", "Edinburgh", "", "Roughly 1 hr drive to Perth (approx.)",
     "Most likely arrival point for flights from Canada — check direct routes."),
    ("Glasgow Airport", "Airport", "Glasgow", "", "Roughly 1 hr 15 drive to Perth (approx.)", ""),
    ("Perth railway station", "Train / bus", "Perth", "", "", "Trains from Edinburgh & Glasgow."),
    ("Dunkeld & Birnam station", "Train / bus", "Dunkeld / Birnam", "", "Walkable to Birnam", "On the Highland Main Line north of Perth."),
]


@transaction.atomic
def run():
    for i, (name, icon, lo, med, hi) in enumerate(BUDGET):
        m.BudgetCategory.objects.create(name=name, icon=icon, order=i, alloc_low=lo, alloc_medium=med, alloc_high=hi)
    cats = {c.name: c for c in m.BudgetCategory.objects.all()}
    for cat, item, est, notes in BUDGET_ITEMS:
        m.BudgetItem.objects.create(category=cats[cat], item=item, estimate=D(est) if est is not None else None, notes=notes)

    for title, cat, owner, prio, due, status, notes in TASKS:
        m.Task.objects.create(title=title, category=cat, owner=owner, priority=prio, due_date=due, status=status, notes=notes)

    for phase, items in TIMELINE.items():
        for i, title in enumerate(items):
            m.TimelineItem.objects.create(phase=phase, title=title, order=i)

    for i, (decision, answer, status, notes) in enumerate(DECISIONS):
        m.Decision.objects.create(decision=decision, answer=answer, status=status, notes=notes, order=i)

    for kind, texts in NOTES.items():
        for i, text in enumerate(texts):
            m.Note.objects.create(kind=kind, text=text, order=i)

    for title, cat, note, tags in reversed(IDEAS):
        m.Idea.objects.create(title=title, category=cat, note=note, tags=tags)

    for name, kind, area, price, distance, notes in TRAVEL:
        m.TravelOption.objects.create(name=name, kind=kind, area=area, price=price, distance=distance, notes=notes, status="Researching")

    hermitage = m.Venue.objects.create(
        name="The Hermitage",
        role="Ceremony",
        location="Dunkeld, Perthshire (National Trust for Scotland)",
        venue_type="Outdoor / woodland",
        website="https://www.nts.org.uk/visit/places/the-hermitage",
        distance_from_perth="~15 miles (approx.)",
        capacity="",
        availability="Unknown",
        status="To Contact",
        outdoor_space="Yes",
        next_follow_up=d(2026, 9, 30),
        rating=5,
        notes="Ideally at / around Ossian's Hall, surrounded by woodland. Intimate, relaxed ceremony with photographs "
              "around the Hermitage afterwards. First priority.",
    )
    m.Enquiry.objects.create(
        venue=hermitage, date=d(2026, 9, 27), kind="Enquiry prepared",
        content="Drafted enquiry asking about:\n• Saturday 29 May 2027 availability\n• alternative dates around the end of May\n"
                "• current pricing\n• what is included",
    )
    m.Venue.objects.create(
        name="Birnam Arts", role="Reception", location="Birnam, by Dunkeld", venue_type="Arts centre",
        distance_from_perth="~15 miles (approx.)", distance_from_ceremony="Very close — a mile or so (approx.)",
        status="To Contact", rating=4,
        notes="Strong option: close to the Hermitage / Dunkeld and already set up for functions.\n\nNeed to find out: "
              "availability on 29 May 2027, wedding hire price, catering rules, alcohol / BYOB rules, capacity, closing time.",
    )
    m.Venue.objects.create(
        name="Murthly Village Hall", role="Reception", location="Murthly", venue_type="Village hall",
        status="Idea", rating=3, notes="Potential lower-cost option.",
    )
    m.Venue.objects.create(
        name="Bachilton Barn / Wed in a Shed", role="Both", location="Perthshire", venue_type="Barn",
        status="Idea", rating=2,
        notes="Lovely, but likely to cost more than the Hermitage + function-room approach.",
    )

    wedding = m.WeddingSettings.load()
    wedding.ceremony_venue = hermitage
    wedding.save()
