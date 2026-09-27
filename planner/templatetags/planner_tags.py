import json
from decimal import Decimal

from django import template
from django.db import models
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from ..registry import kind_for

register = template.Library()


def _plain_number(value):
    if value is None:
        return ""
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return str(value.quantize(Decimal(1)))
    return str(value)


@register.simple_tag
def edit(obj, field_name, label=None, cls="", placeholder="", rows=3):
    """Render a form control for one field that saves itself as soon as it changes.

    {% edit task "status" %}             bare control, e.g. in a table cell
    {% edit venue "capacity" label=True %} control with its label above it
    """
    slug, _ = kind_for(obj)
    f = obj._meta.get_field(field_name)
    url = reverse("field_update", args=[slug, obj.pk])
    dom_id = f"f-{slug}-{obj.pk}-{field_name}"
    value = getattr(obj, f.attname)
    trigger = "change"

    attrs = {
        "id": dom_id,
        "name": field_name,
        "hx-post": url,
        "hx-swap": "none",
        "hx-vals": json.dumps({"_field": field_name}),
        "data-autosave": "",
        "class": f"ctl {cls}".strip(),
        "aria-label": f.verbose_name.capitalize(),
    }
    if placeholder:
        attrs["placeholder"] = placeholder

    def attr_html():
        return format_html_join(" ", '{}="{}"', attrs.items())

    if f.choices or isinstance(f, models.ForeignKey):
        options = f.get_choices(include_blank=f.null or f.blank) if isinstance(f, models.ForeignKey) else f.choices
        attrs["data-value"] = "" if value is None else str(value)
        attrs["class"] += " ctl-select"
        opts = format_html_join(
            "",
            '<option value="{}"{}>{}</option>',
            ((k if k != "" else "", mark_safe(" selected") if str(k) == str(value if value is not None else "") else "", v)
             for k, v in options),
        )
        control = format_html("<select {}>{}</select>", attr_html(), opts)
    elif isinstance(f, models.BooleanField):
        attrs["type"] = "checkbox"
        attrs["class"] += " ctl-check"
        attrs["value"] = "on"
        control = format_html("<input {}{}>", attr_html(), mark_safe(" checked") if value else "")
    elif isinstance(f, models.TextField):
        attrs["hx-trigger"] = "input changed delay:1200ms, change"
        attrs["rows"] = rows
        attrs["class"] += " ctl-area"
        control = format_html("<textarea {}>{}</textarea>", attr_html(), value or "")
    else:
        if isinstance(f, models.DateField):
            attrs["type"] = "date"
            attrs["value"] = value.isoformat() if value else ""
        elif isinstance(f, (models.DecimalField, models.IntegerField)):
            attrs["type"] = "number"
            attrs["inputmode"] = "decimal" if isinstance(f, models.DecimalField) else "numeric"
            attrs["step"] = "0.01" if isinstance(f, models.DecimalField) else "1"
            attrs["min"] = "0"
            attrs["value"] = _plain_number(value)
            attrs["class"] += " ctl-num"
        elif isinstance(f, models.URLField):
            attrs["type"] = "url"
            attrs["value"] = value or ""
            attrs.setdefault("placeholder", "https://…")
        else:
            attrs["type"] = "text"
            attrs["value"] = value or ""
        control = format_html("<input {}>", attr_html())

    if not label:
        return control
    text = label if isinstance(label, str) else f.verbose_name[:1].upper() + f.verbose_name[1:]
    hint = format_html('<small class="hint">{}</small>', f.help_text) if f.help_text else ""
    if isinstance(f, models.BooleanField):
        return format_html('<label class="field field-check" for="{}">{}<span>{}</span>{}</label>', dom_id, control, text, hint)
    return format_html('<label class="field" for="{}"><span>{}</span>{}{}</label>', dom_id, text, control, hint)


@register.filter
def money(value, pennies=False):
    """£1,250 — pennies only if there are any."""
    if value in (None, ""):
        return "—"
    value = Decimal(value)
    if value == value.to_integral_value() and not pennies:
        return f"£{value:,.0f}"
    return f"£{value:,.2f}"


@register.filter
def pct(part, whole):
    try:
        return max(0, min(100, round(float(part) / float(whole) * 100)))
    except (TypeError, ZeroDivisionError, ValueError):
        return 0


PEOPLE = {
    "richard": ("R", "Richard", "p-richard"),
    "denver": ("D", "Denver", "p-denver"),
    "both": ("R+D", "Both of us", "p-both"),
}


@register.simple_tag
def avatar(who, size=""):
    """Little initial bubble for Richard, Denver, or both. Accepts a User or a name."""
    if who is None:
        return ""
    key = (getattr(who, "username", None) or str(who)).lower()
    if key not in PEOPLE:
        return ""
    initials, name, cls = PEOPLE[key]
    return format_html('<span class="avatar {} {}" title="{}">{}</span>', cls, size, name, initials)


@register.filter
def slug(obj):
    return kind_for(obj)[0]


@register.filter
def status_class(value):
    return "s-" + "".join(c if c.isalnum() else "-" for c in str(value).lower()).strip("-")


@register.filter
def get(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def dash_if_empty(value):
    return value if value not in (None, "") else "—"


@register.filter
def absval(value):
    try:
        return abs(value)
    except TypeError:
        return value
