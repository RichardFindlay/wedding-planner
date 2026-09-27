from .models import WeddingSettings

NAV = [
    ("dashboard", "Home", "🏡"),
    ("tasks", "Tasks", "✅"),
    ("budget", "Budget", "💷"),
    ("venues", "Venues", "🏠"),
    ("enquiries", "Enquiries", "💌"),
    ("guests", "Guests", "👥"),
    ("ideas", "Ideas", "🌿"),
    ("suppliers", "Suppliers", "📞"),
    ("travel", "Travel", "✈️"),
    ("timeline", "Timeline", "📅"),
    ("decisions", "Decisions", "⚖️"),
    ("notes", "Love / Avoid", "💚"),
]

# The five that sit in the phone's bottom bar; everything else lives under "More".
MOBILE_NAV = ["dashboard", "tasks", "budget", "venues", "ideas"]


def wedding(request):
    if not request.user.is_authenticated:
        return {}
    match = getattr(request, "resolver_match", None)
    return {
        "wedding": WeddingSettings.load(),
        "nav": NAV,
        "mobile_nav": [n for n in NAV if n[0] in MOBILE_NAV],
        "current": match.url_name if match else "",
    }
