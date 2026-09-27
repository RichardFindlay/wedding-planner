import datetime
import io
import json
from collections import OrderedDict
from decimal import Decimal
from itertools import chain
from urllib.parse import parse_qs, urlparse

from django import forms
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_not_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import models
from django.db.models import ProtectedError, Q
from django.forms import modelform_factory
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from .registry import KINDS

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_kind(slug):
    if slug not in KINDS:
        raise Http404
    return KINDS[slug]


def hx_response(content="", triggers=None, **headers):
    resp = HttpResponse(content)
    if triggers:
        resp["HX-Trigger"] = json.dumps(triggers)
    for k, v in headers.items():
        resp[k.replace("_", "-")] = v
    return resp


def _formfield(f, **kwargs):
    """Nicer default widgets for quick-add forms."""
    if isinstance(f, models.DateField):
        kwargs["widget"] = forms.DateInput(attrs={"type": "date"})
    elif isinstance(f, models.TextField):
        kwargs["widget"] = forms.Textarea(attrs={"rows": 4})
    return f.formfield(**kwargs)


def save_image(upload):
    """Shrink phone photos / screenshots to something sensible and store them."""
    from PIL import Image as PILImage, ImageOps

    img = PILImage.open(upload)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return m.Image.objects.create(data=buf.getvalue(), mime="image/jpeg", width=img.width, height=img.height)


# ---------------------------------------------------------------------------
# Derived numbers used in several places
# ---------------------------------------------------------------------------


SCENARIO_BLURBS = {
    "low": "Very DIY — simple hall, inexpensive food, our own drinks, few suppliers.",
    "medium": "The sweet spot — Hermitage, nice function room, good informal food, photographer, ceilidh.",
    "high": "Better catering, more photography, transport, flowers — less DIY, less stress.",
}


def budget_context():
    wedding = m.WeddingSettings.load()
    scenario = wedding.scenario
    categories = list(m.BudgetCategory.objects.prefetch_related("items"))
    rows = []
    totals = {"allocated": Decimal(0), "forecast": Decimal(0), "committed": Decimal(0), "paid": Decimal(0), "remaining": Decimal(0)}
    for cat in categories:
        items = list(cat.items.all())
        row = {
            "category": cat,
            "items": items,
            "allocated": cat.allocation(scenario),
            "forecast": sum((i.forecast for i in items), Decimal(0)),
            "committed": sum((i.committed for i in items), Decimal(0)),
            "paid": sum((i.paid or 0 for i in items), Decimal(0)),
            "remaining": sum((i.remaining for i in items), Decimal(0)),
        }
        row["over"] = row["forecast"] > row["allocated"] and row["allocated"] > 0
        rows.append(row)
        for k in totals:
            totals[k] += row[k]
    target = wedding.target
    scale = max(target, totals["forecast"], Decimal(1))
    paid = min(totals["paid"], totals["forecast"])
    committed = max(min(totals["committed"], totals["forecast"]) - paid, Decimal(0))
    bar = {
        "paid": float(paid / scale * 100),
        "committed": float(committed / scale * 100),
        "forecast": float(max(totals["forecast"] - paid - committed, Decimal(0)) / scale * 100),
        "target": float(target / scale * 100),
    }
    scenario_cards = []
    for key, label in m.SCENARIOS:
        t = getattr(wedding, f"target_{key}")
        scenario_cards.append({
            "key": key,
            "label": label,
            "target": t,
            "allocated": sum((c.allocation(key) for c in categories), Decimal(0)),
            "diff": t - totals["forecast"],
            "desc": SCENARIO_BLURBS[key],
        })
    ctx = {
        "bar": bar,
        "scenario_cards": scenario_cards,
        "wedding": wedding,
        "scenario": scenario,
        "scenarios": m.SCENARIOS,
        "target": target,
        "rows": rows,
        "totals": totals,
        "headroom": target - totals["forecast"],
        "unallocated": target - totals["allocated"],
        "upcoming_payments": m.BudgetItem.objects.filter(payment_due__isnull=False)
        .exclude(status__in=["Paid in full", "Not needed"])
        .order_by("payment_due")[:5],
    }
    ctx["budget_self"] = ctx  # lets shared partials take the whole thing as one variable
    return ctx


def guest_stats():
    guests = list(m.Guest.objects.all())
    heads = lambda qs: sum(g.headcount for g in qs)  # noqa: E731
    invited = [g for g in guests if g.rsvp != "Not invited yet"]
    return {
        "people": heads(guests),
        "records": len(guests),
        "invited": heads(invited),
        "confirmed": heads(g for g in guests if g.rsvp == "Confirmed"),
        "declined": heads(g for g in guests if g.rsvp == "Declined"),
        "pending": heads(g for g in guests if g.rsvp in ("Invited", "Maybe")),
        "canada": heads(g for g in guests if g.from_canada),
        "accommodation": heads(g for g in guests if g.accommodation),
        "transport": heads(g for g in guests if g.transport),
        "dietary": sum(1 for g in guests if g.dietary),
        "ceremony": heads(g for g in guests if g.ceremony),
        "evening": heads(g for g in guests if g.evening),
        "richard": heads(g for g in guests if g.side == "Richard"),
        "denver": heads(g for g in guests if g.side == "Denver"),
    }


def task_progress():
    tasks = m.Task.objects.exclude(status="Not Going Ahead")
    total = tasks.count()
    done = tasks.filter(status__in=m.DONE_STATUSES).count()
    started = tasks.filter(status__in=["Researching", "Waiting for Reply", "In Progress"]).count()
    todo = total - done - started
    # Donut segments (r=54 → circumference ≈ 339.3), with a small gap between each.
    circ, gap = 339.29, 3
    segments, offset = [], 0.0
    for label, n, colour in (("Completed", done, "#2f5a43"), ("In progress", started, "#86a98a"), ("Not started", todo, "#dce6d6")):
        length = circ * n / total if total else 0
        if n:
            segments.append({"label": label, "n": n, "colour": colour,
                             "dash": f"{max(length - gap, 1):.2f} {circ:.2f}", "offset": f"{-offset:.2f}"})
        offset += length
    return {"total": total, "done": done, "started": started, "todo": todo, "segments": segments,
            "pct": round(done / total * 100) if total else 0}


def priority_key(t):
    return (
        0 if t.is_overdue else 1,
        m.PRIORITY_ORDER.get(t.priority, 9),
        t.due_date or datetime.date.max,
        t.created_at,
    )


def current_phase():
    today = timezone.localdate()
    phase = m.TIMELINE_PHASES[0][0]
    for key, _label, start in m.TIMELINE_PHASES:
        if start <= today:
            phase = key
    return phase


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@login_not_required
def healthz(request):
    return JsonResponse({"ok": True})


@login_not_required
def who(request):
    """No passwords: just pick who you are, remembered on this device."""
    if request.method == "POST":
        user = User.objects.filter(username=request.POST.get("who"), username__in=["richard", "denver"]).first()
        if user:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            nxt = request.POST.get("next", "")
            return redirect(nxt if url_has_allowed_host_and_scheme(nxt, {request.get_host()}) else "dashboard")
    return render(request, "planner/login.html", {"next": request.GET.get("next", "")})


def dashboard(request):
    wedding = m.WeddingSettings.load()
    open_tasks = sorted(m.Task.objects.exclude(status__in=m.CLOSED_STATUSES), key=priority_key)
    follow_ups = sorted(
        [v for v in chain(m.Venue.objects.filter(next_follow_up__isnull=False), m.Supplier.objects.filter(next_follow_up__isnull=False))
         if v.status not in ("Rejected", "Booked")],
        key=lambda v: v.next_follow_up,
    )[:4]

    ceremony, reception = wedding.ceremony_venue, wedding.reception_venue
    journey = [
        {"icon": "tree", "title": ceremony.name if ceremony else "Ceremony venue TBC", "sub": "Ceremony", "venue": ceremony},
        {"icon": "bubbles", "title": "Photos & bubbles", "sub": f"Around {ceremony.name}" if ceremony else "Somewhere beautiful", "venue": None},
        {"icon": "plate", "title": reception.name if reception else "Reception venue TBC", "sub": "Reception", "venue": reception},
        {"icon": "dance", "title": "Ceilidh & party", "sub": reception.name if reception else "Dancing til late", "venue": None},
    ]

    stats = guest_stats()
    guest_line = (
        f"{stats['people']} on the list" if stats["people"] else (f"~{wedding.guest_estimate} (rough)" if wedding.guest_estimate else "TBC")
    )

    def venue_decision(v, role):
        if not v:
            shortlisted = m.Venue.objects.filter(role__in=[role, "Both"]).exclude(status="Rejected").count()
            return "TBC", f"{shortlisted} option{'s' if shortlisted != 1 else ''} being considered"
        if v.status == "Booked":
            return v.name, "Booked 🎉"
        return v.name, f"{v.status} · availability {v.availability.lower()}"

    key_decisions = [
        ("Ceremony", *venue_decision(ceremony, "Ceremony")),
        ("Reception", *venue_decision(reception, "Reception")),
        ("Guest count", guest_line, f"{stats['confirmed']} confirmed" if stats["confirmed"] else "Nothing confirmed yet"),
        ("Budget", f"{dict(m.SCENARIOS)[wedding.scenario]} · £{wedding.target:,.0f}", "Working target"),
    ]

    recent = sorted(
        chain(*(k.model.objects.order_by("-updated_at")[:6] for s, k in KINDS.items() if s not in ("settings", "budgetcategory"))),
        key=lambda o: o.updated_at,
        reverse=True,
    )[:6]

    return render(request, "planner/dashboard.html", {
        "budget": budget_context(),
        "progress": task_progress(),
        "priorities": open_tasks[:5],
        "follow_ups": follow_ups,
        "journey": journey,
        "key_decisions": key_decisions,
        "guest": stats,
        "recent": recent,
        "ideas": m.Idea.objects.select_related("image")[:4],
        "phase": dict((k, l) for k, l, _ in m.TIMELINE_PHASES)[current_phase()],
        "phase_items": m.TimelineItem.objects.filter(phase=current_phase()),
    })


TASK_SORTS = {
    "priority": priority_key,
    "due": lambda t: (t.due_date or datetime.date.max, m.PRIORITY_ORDER.get(t.priority, 9)),
    "status": lambda t: [s for s, _ in m.TASK_STATUSES].index(t.status),
    "category": lambda t: (t.category, m.PRIORITY_ORDER.get(t.priority, 9)),
    "owner": lambda t: (t.owner, m.PRIORITY_ORDER.get(t.priority, 9)),
    "title": lambda t: t.title.lower(),
}


def tasks(request):
    show = request.GET.get("show", "open")
    qs = m.Task.objects.all()
    if show == "open":
        qs = qs.exclude(status__in=m.CLOSED_STATUSES)
    elif show == "done":
        qs = qs.filter(status__in=m.CLOSED_STATUSES)
    filters = {}
    for f in ("owner", "category", "priority", "status"):
        v = request.GET.get(f)
        if v:
            filters[f] = v
            qs = qs.filter(**{f: v})
    sort = request.GET.get("sort", "priority")
    items = sorted(qs, key=TASK_SORTS.get(sort, priority_key))
    return render(request, "planner/tasks.html", {
        "tasks": items,
        "show": show,
        "sort": sort,
        "filters": filters,
        "progress": task_progress(),
        "owner_choices": m.OWNER_CHOICES,
        "category_choices": m.TASK_CATEGORIES,
        "priority_choices": m.PRIORITY_CHOICES,
        "status_choices": m.TASK_STATUSES,
        "sorts": [("priority", "Most urgent"), ("due", "Due date"), ("status", "Status"), ("category", "Category"), ("owner", "Owner"), ("title", "A–Z")],
    })


def budget(request):
    return render(request, "planner/budget.html", budget_context())


VENUE_LANES = [
    ("Ideas", ["Idea", "To Contact"], "To Contact"),
    ("In conversation", ["Enquiry Sent", "Awaiting Reply", "Replied", "Viewing Booked"], "Enquiry Sent"),
    ("Shortlisted", ["Shortlisted"], "Shortlisted"),
    ("Booked", ["Booked"], "Booked"),
    ("Ruled out", ["Rejected"], "Rejected"),
]


def venues(request):
    role = request.GET.get("role", "")
    view = request.GET.get("view", "board")
    qs = m.Venue.objects.all()
    if role:
        qs = qs.filter(role__in=[role, "Both"])
    venues = list(qs)
    lanes = [
        {"name": name, "drop_status": drop, "venues": [v for v in venues if v.status in statuses]}
        for name, statuses, drop in VENUE_LANES
    ]
    return render(request, "planner/venues.html", {
        "venues": [v for v in venues if v.status != "Rejected"] + [v for v in venues if v.status == "Rejected"],
        "lanes": lanes,
        "role": role,
        "view": view,
    })


def venue_detail(request, pk):
    venue = get_object_or_404(m.Venue, pk=pk)
    return render(request, "planner/venue_detail.html", {"venue": venue, "subject": venue, "subject_slug": "venue", "enquiry_kinds": m.ENQUIRY_KINDS})


def suppliers(request):
    view = request.GET.get("view", "cards")
    category = request.GET.get("category", "")
    qs = m.Supplier.objects.all()
    if category:
        qs = qs.filter(category=category)
    groups = OrderedDict((c, []) for c, _ in m.SUPPLIER_CATEGORIES)
    for s in qs:
        groups[s.category].append(s)
    return render(request, "planner/suppliers.html", {
        "groups": [(c, items) for c, items in groups.items() if items],
        "empty_categories": [c for c, items in groups.items() if not items and not category],
        "category": category,
        "categories": m.SUPPLIER_CATEGORIES,
        "view": view,
    })


def supplier_detail(request, pk):
    supplier = get_object_or_404(m.Supplier, pk=pk)
    return render(request, "planner/supplier_detail.html", {"supplier": supplier, "subject": supplier, "subject_slug": "supplier", "enquiry_kinds": m.ENQUIRY_KINDS})


def enquiries(request):
    today = timezone.localdate()
    subjects = [s for s in chain(m.Venue.objects.all(), m.Supplier.objects.all()) if s.status not in ("Rejected", "Booked")]
    due = sorted([s for s in subjects if s.next_follow_up and s.next_follow_up <= today], key=lambda s: s.next_follow_up)
    upcoming = sorted([s for s in subjects if s.next_follow_up and s.next_follow_up > today], key=lambda s: s.next_follow_up)
    waiting = [s for s in subjects if s.status in ("Enquiry Sent", "Awaiting Reply") and not s.next_follow_up]
    to_contact = [s for s in subjects if s.status == "To Contact"]
    log = m.Enquiry.objects.select_related("venue", "supplier", "created_by")
    return render(request, "planner/enquiries.html", {
        "due": due, "upcoming": upcoming, "waiting": waiting, "to_contact": to_contact, "log": log,
    })


def guests(request):
    qs = m.Guest.objects.all()
    side = request.GET.get("side", "")
    flag = request.GET.get("flag", "")
    rsvp = request.GET.get("rsvp", "")
    if side:
        qs = qs.filter(side=side)
    if rsvp:
        qs = qs.filter(rsvp=rsvp)
    if flag in ("from_canada", "accommodation", "transport", "plus_one"):
        qs = qs.filter(**{flag: True})
    elif flag == "dietary":
        qs = qs.exclude(dietary="")
    return render(request, "planner/guests.html", {
        "guests": qs, "stats": guest_stats(), "side": side, "flag": flag, "rsvp": rsvp,
        "rsvp_choices": m.RSVP_CHOICES,
    })


def ideas(request):
    qs = m.Idea.objects.select_related("image", "created_by")
    category = request.GET.get("category", "")
    tag = request.GET.get("tag", "")
    if category:
        qs = qs.filter(category=category)
    if tag:
        qs = qs.filter(tags__icontains=tag)
    if request.GET.get("loved"):
        qs = qs.filter(Q(loved_by_richard=True) | Q(loved_by_denver=True))
    counts = {c: 0 for c, _ in m.IDEA_CATEGORIES}
    for c in m.Idea.objects.values_list("category", flat=True):
        counts[c] = counts.get(c, 0) + 1
    return render(request, "planner/ideas.html", {
        "ideas": qs, "category": category, "tag": tag, "loved": bool(request.GET.get("loved")),
        "categories": [(c, counts.get(c, 0)) for c, _ in m.IDEA_CATEGORIES],
    })


def travel(request):
    groups = OrderedDict()
    for t in m.TravelOption.objects.all():
        section = "Staying" if t.kind in ("Hotel", "Airbnb / cottage", "B&B") else "Getting here & around"
        groups.setdefault(section, []).append(t)
    canada = m.Guest.objects.filter(from_canada=True)
    return render(request, "planner/travel.html", {
        "groups": groups.items(),
        "canada_people": sum(g.headcount for g in canada),
        "canada_rooms": sum(1 for g in canada if g.accommodation),
    })


def timeline(request):
    now_key = current_phase()
    items = list(m.TimelineItem.objects.all())
    tasks = list(m.Task.objects.filter(due_date__isnull=False))
    phases = []
    for i, (key, label, start) in enumerate(m.TIMELINE_PHASES):
        end = m.TIMELINE_PHASES[i + 1][2] if i + 1 < len(m.TIMELINE_PHASES) else datetime.date.max
        phase_items = [t for t in items if t.phase == key]
        phases.append({
            "key": key,
            "label": label,
            "start": start,
            "items": phase_items,
            "done": sum(1 for t in phase_items if t.done),
            "tasks": sorted([t for t in tasks if start <= t.due_date < end], key=lambda t: t.due_date),
            "is_now": key == now_key,
            "is_past": start < dict((k, s) for k, _, s in m.TIMELINE_PHASES)[now_key],
        })
    return render(request, "planner/timeline.html", {"phases": phases})


def decisions(request):
    return render(request, "planner/decisions.html", {"decisions": m.Decision.objects.all()})


def notes(request):
    groups = [(k, label, m.Note.objects.filter(kind=k)) for k, label in m.NOTE_KINDS]
    return render(request, "planner/notes.html", {"groups": groups})


def search(request):
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        specs = [
            (m.Task, ["title", "notes", "category"], "task", "Task"),
            (m.Venue, ["name", "location", "notes", "catering"], "venue", "Venue"),
            (m.Supplier, ["name", "category", "notes"], "supplier", "Supplier"),
            (m.Guest, ["name", "group", "relationship", "notes", "dietary"], "guest", "Guest"),
            (m.Idea, ["title", "note", "tags", "category"], "idea", "Idea"),
            (m.BudgetItem, ["item", "notes"], "budgetitem", "Budget"),
            (m.TravelOption, ["name", "notes", "area"], "travel", "Travel"),
            (m.Decision, ["decision", "answer", "notes"], "decision", "Decision"),
            (m.Note, ["text"], "note", "Note"),
            (m.Enquiry, ["content"], "enquiry", "Enquiry"),
            (m.TimelineItem, ["title"], "timeline", "Timeline"),
        ]
        for model, fields, slug, label in specs:
            cond = Q()
            for f in fields:
                cond |= Q(**{f"{f}__icontains": q})
            for obj in model.objects.filter(cond)[:6]:
                results.append({"label": label, "title": str(obj), "url": result_url(slug, obj), "obj": obj})
    return render(request, "planner/partials/search_results.html", {"q": q, "results": results[:24]})


def result_url(slug, obj):
    kind = KINDS[slug]
    if kind.detail_page:
        return obj.get_absolute_url()
    if slug == "enquiry":
        return obj.subject.get_absolute_url()
    if slug in ("decision", "note", "timeline"):
        return reverse(kind.list_url) + f"#{slug}-{obj.pk}"
    return reverse(kind.list_url) + f"?open={slug}:{obj.pk}"


# ---------------------------------------------------------------------------
# Generic editing endpoints (used by every page via htmx)
# ---------------------------------------------------------------------------

# Extra bits of the page to refresh after a field changes, keyed by record type.
OOB_CONTEXT = {
    "budgetitem": lambda obj: budget_context(),
    "budgetcategory": lambda obj: budget_context(),
    "guest": lambda obj: {"stats": guest_stats()},
    "task": lambda obj: {"progress": task_progress()},
}


@require_POST
def field_update(request, slug, pk):
    kind = get_kind(slug)
    obj = get_object_or_404(kind.model, pk=pk)
    name = request.POST.get("_field", "")
    try:
        f = kind.model._meta.get_field(name)
    except Exception:
        raise Http404
    if not f.editable or f.primary_key or f.auto_created:
        raise Http404

    Form = modelform_factory(kind.model, fields=[name])
    form = Form(request.POST, instance=obj)
    if not form.is_valid():
        msg = "; ".join(e for errs in form.errors.values() for e in errs)
        return hx_response(triggers={"planner:error": f"{f.verbose_name.capitalize()}: {msg}"})

    obj = form.save(commit=False)
    obj.updated_by = request.user
    obj.save()

    triggers = {"planner:saved": {"id": f"f-{slug}-{pk}-{name}"}, "planner:changed": {}}
    if slug == "settings":
        triggers["planner:refresh"] = {}

    content = ""
    try:
        tpl = get_template(f"planner/oob/{slug}.html")
    except TemplateDoesNotExist:
        tpl = None
    if tpl:
        # Keep the page's filters (e.g. ?flag=from_canada) when re-rendering bits of it.
        page_query = urlparse(request.headers.get("HX-Current-URL", "")).query
        ctx = {k: v[0] for k, v in parse_qs(page_query).items() if k in ("flag", "rsvp", "side")}
        ctx.update({"obj": obj, "oob": True})
        if slug in OOB_CONTEXT:
            ctx.update(OOB_CONTEXT[slug](obj))
        content = tpl.render(ctx, request)
    return hx_response(content, triggers)


def create(request, slug):
    kind = get_kind(slug)
    Form = modelform_factory(kind.model, fields=kind.quick_fields, formfield_callback=_formfield)
    prefilled = [k for k in request.GET if k in kind.quick_fields]
    if slug == "enquiry" and ("venue" in prefilled or "supplier" in prefilled):
        prefilled = list({*prefilled, "venue", "supplier"})

    if request.method == "POST":
        form = Form(request.POST)
        prefilled = [k for k in request.POST.getlist("_hidden") if k in kind.quick_fields]
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = obj.updated_by = request.user
            if slug == "idea" and request.FILES.get("upload"):
                obj.image = save_image(request.FILES["upload"])
            obj.save()
            if slug == "enquiry":
                apply_enquiry(obj, request.user)
            if kind.detail_page:
                return hx_response(HX_Redirect=obj.get_absolute_url())
            return hx_response(triggers={"planner:created": {"message": f"Added {kind.label}: {obj}"}}, HX_Reswap="none")
    else:
        form = Form(initial={k: request.GET.get(k, "") for k in prefilled})

    return render(request, "planner/partials/new_form.html", {
        "form": form, "kind": kind, "slug": slug, "hidden": prefilled,
    })


# How logging an enquiry moves a venue/supplier along.
STATUS_ORDER = ["Idea", "To Contact", "Enquiry Sent", "Awaiting Reply", "Replied", "Viewing Booked", "Shortlisted", "Booked"]
KIND_TO_STATUS = {
    "Enquiry sent": "Awaiting Reply",
    "Follow-up sent": "Awaiting Reply",
    "Reply received": "Replied",
    "Quote received": "Replied",
    "Phone call": "Replied",
    "Viewing": "Viewing Booked",
    "Booked": "Booked",
}


def apply_enquiry(entry, user):
    subject = entry.subject
    if not subject:
        return
    new_status = KIND_TO_STATUS.get(entry.kind)
    if new_status and subject.status != "Rejected":
        cur = STATUS_ORDER.index(subject.status) if subject.status in STATUS_ORDER else 0
        if STATUS_ORDER.index(new_status) > cur:
            subject.status = new_status
    if entry.kind in ("Enquiry sent", "Follow-up sent"):
        # Nudge ourselves in a week if we hear nothing.
        subject.next_follow_up = entry.date + datetime.timedelta(days=7)
    elif entry.kind in ("Reply received", "Quote received", "Booked"):
        subject.next_follow_up = None
    if entry.kind == "Booked" and isinstance(subject, m.Supplier):
        subject.booked = True
    subject.updated_by = user
    subject.save()


@require_POST
def delete(request, slug, pk):
    kind = get_kind(slug)
    obj = get_object_or_404(kind.model, pk=pk)
    try:
        obj.delete()
    except ProtectedError:
        return hx_response(triggers={"planner:error": "Move or delete the items in this category first."})
    if kind.detail_page and request.POST.get("from") == "detail":
        return hx_response(HX_Redirect=reverse(kind.list_url))
    return hx_response(triggers={"planner:deleted": {"message": f"Deleted {kind.label}"}, "planner:changed": {}})


def drawer(request, slug, pk):
    kind = get_kind(slug)
    obj = get_object_or_404(kind.model, pk=pk)
    return render(request, "planner/partials/drawer.html", {"obj": obj, "kind": kind, "slug": slug, "fields": kind.drawer_fields})


@require_POST
def idea_image(request, pk):
    idea = get_object_or_404(m.Idea, pk=pk)
    if request.POST.get("remove"):
        idea.image = None
    elif request.FILES.get("upload"):
        idea.image = save_image(request.FILES["upload"])
    idea.updated_by = request.user
    idea.save()
    resp = render(request, "planner/partials/drawer.html", {"obj": idea, "kind": KINDS["idea"], "slug": "idea", "fields": KINDS["idea"].drawer_fields})
    resp["HX-Trigger"] = json.dumps({"planner:changed": {}})
    return resp


@require_POST
def idea_love(request, pk):
    idea = get_object_or_404(m.Idea, pk=pk)
    field = f"loved_by_{request.user.username}"
    if hasattr(idea, field):
        setattr(idea, field, not getattr(idea, field))
        idea.save(update_fields=[field])
    return render(request, "planner/partials/hearts.html", {"idea": idea})


def image(request, pk):
    img = get_object_or_404(m.Image, pk=pk)
    resp = HttpResponse(bytes(img.data), content_type=img.mime)
    resp["Cache-Control"] = "private, max-age=31536000, immutable"
    return resp
