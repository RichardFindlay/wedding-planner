import datetime
import io
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image as PILImage

from . import models as m

PAGES = [
    "dashboard", "tasks", "budget", "venues", "suppliers", "enquiries", "guests", "ideas",
    "travel", "timeline", "decisions", "notes",
]


@override_settings(ALLOWED_HOSTS=["testserver"])
class PlannerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_wedding", stdout=io.StringIO())

    def setUp(self):
        self.client.post(reverse("login"), {"who": "denver"})
        self.denver = get_user_model().objects.get(username="denver")

    def field(self, slug, obj, name, value):
        return self.client.post(
            reverse("field_update", args=[slug, obj.pk]), {"_field": name, name: value}, HTTP_HX_REQUEST="true"
        )

    # -- access -------------------------------------------------------------

    def test_pages_need_someone_picked(self):
        self.client.post(reverse("logout"))
        resp = self.client.get(reverse("tasks"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp["Location"])

    def test_only_richard_or_denver_can_be_picked(self):
        self.client.post(reverse("logout"))
        get_user_model().objects.create_user("intruder")
        self.client.post(reverse("login"), {"who": "intruder"})
        self.assertEqual(self.client.get(reverse("tasks")).status_code, 302)

    def test_every_page_renders(self):
        for name in PAGES:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        venue = m.Venue.objects.first()
        self.assertEqual(self.client.get(venue.get_absolute_url()).status_code, 200)

    def test_seed_loaded_once(self):
        self.assertTrue(m.Venue.objects.filter(name="The Hermitage").exists())
        call_command("setup_wedding", stdout=io.StringIO())
        self.assertEqual(m.Venue.objects.filter(name="The Hermitage").count(), 1)
        self.assertEqual(m.WeddingSettings.load().ceremony_venue.name, "The Hermitage")

    def test_seed_prices_are_estimates_not_quotes(self):
        self.assertFalse(m.BudgetItem.objects.filter(quote__isnull=False).exists())
        self.assertFalse(m.Venue.objects.filter(price_quote__isnull=False).exists())

    # -- inline editing -----------------------------------------------------

    def test_field_update_saves_and_records_who(self):
        task = m.Task.objects.first()
        resp = self.field("task", task, "status", "Completed")
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "Completed")
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.updated_by, self.denver)
        self.assertIn("planner:saved", json.loads(resp["HX-Trigger"]))

    def test_unticking_clears_completion(self):
        task = m.Task.objects.first()
        self.field("task", task, "status", "Completed")
        self.field("task", task, "status", "Not Started")
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)

    def test_checkbox_off_is_saved_as_false(self):
        guest = m.Guest.objects.create(name="Test Guest", from_canada=True)
        self.client.post(reverse("field_update", args=["guest", guest.pk]), {"_field": "from_canada"})
        guest.refresh_from_db()
        self.assertFalse(guest.from_canada)

    def test_invalid_value_reports_error_without_saving(self):
        venue = m.Venue.objects.first()
        resp = self.field("venue", venue, "website", "not a url")
        self.assertIn("planner:error", json.loads(resp["HX-Trigger"]))
        venue.refresh_from_db()
        self.assertNotEqual(venue.website, "not a url")

    def test_cannot_edit_system_fields(self):
        task = m.Task.objects.first()
        resp = self.field("task", task, "created_by", str(self.denver.pk))
        self.assertEqual(resp.status_code, 404)

    def test_budget_edit_returns_refreshed_totals(self):
        item = m.BudgetItem.objects.exclude(estimate=None).first()
        resp = self.field("budgetitem", item, "booked_cost", "700")
        self.assertContains(resp, 'id="budget-summary"')
        item.refresh_from_db()
        self.assertEqual(item.certainty, "Booked")
        self.assertEqual(item.forecast, Decimal("700"))

    def test_scenario_switch_changes_target(self):
        wedding = m.WeddingSettings.load()
        resp = self.field("settings", wedding, "scenario", "high")
        self.assertIn("planner:refresh", json.loads(resp["HX-Trigger"]))
        self.assertEqual(m.WeddingSettings.load().target, Decimal("8000"))

    def test_seed_scenarios_add_up(self):
        cats = m.BudgetCategory.objects.all()
        self.assertEqual(sum(c.alloc_medium for c in cats), Decimal("5000"))
        self.assertEqual(sum(c.alloc_high for c in cats), Decimal("8000"))

    # -- creating ---------------------------------------------------------

    def test_quick_add_task(self):
        resp = self.client.post(reverse("create", args=["task"]), {
            "title": "Taste cake", "category": "Food & Drink", "owner": "Both", "priority": "Low", "due_date": "",
        })
        self.assertIn("planner:created", json.loads(resp["HX-Trigger"]))
        task = m.Task.objects.get(title="Taste cake")
        self.assertEqual(task.created_by, self.denver)

    def test_quick_add_venue_goes_to_its_page(self):
        resp = self.client.post(reverse("create", args=["venue"]), {
            "name": "Dunkeld Hall", "role": "Reception", "location": "Dunkeld", "venue_type": "Village hall", "website": "",
        })
        venue = m.Venue.objects.get(name="Dunkeld Hall")
        self.assertEqual(resp["HX-Redirect"], venue.get_absolute_url())

    def test_logging_sent_enquiry_moves_venue_along_and_sets_follow_up(self):
        venue = m.Venue.objects.get(name="Birnam Arts")
        self.client.post(reverse("create", args=["enquiry"]), {
            "venue": venue.pk, "date": "2026-10-01", "kind": "Enquiry sent", "content": "Hi there…",
        })
        venue.refresh_from_db()
        self.assertEqual(venue.status, "Awaiting Reply")
        self.assertEqual(venue.next_follow_up, datetime.date(2026, 10, 8))

        self.client.post(reverse("create", args=["enquiry"]), {
            "venue": venue.pk, "date": "2026-10-03", "kind": "Reply received", "content": "Yes, we're free!",
        })
        venue.refresh_from_db()
        self.assertEqual(venue.status, "Replied")
        self.assertIsNone(venue.next_follow_up)
        self.assertEqual(venue.enquiries.count(), 2)

    def test_enquiry_needs_a_subject(self):
        before = m.Enquiry.objects.count()
        resp = self.client.post(reverse("create", args=["enquiry"]), {"date": "2026-10-01", "kind": "Note", "content": "?"})
        self.assertEqual(m.Enquiry.objects.count(), before)
        self.assertContains(resp, "Pick the venue or supplier")

    def test_idea_with_uploaded_image(self):
        buf = io.BytesIO()
        PILImage.new("RGB", (2400, 1200), "green").save(buf, "PNG")
        buf.seek(0)
        buf.name = "shot.png"
        self.client.post(reverse("create", args=["idea"]), {
            "title": "Moss tables", "category": "Decorations", "note": "", "link": "", "tags": "moss", "upload": buf,
        })
        idea = m.Idea.objects.get(title="Moss tables")
        self.assertEqual((idea.image.width, idea.image.height), (1600, 800))
        resp = self.client.get(idea.image.get_absolute_url())
        self.assertEqual(resp["Content-Type"], "image/jpeg")

    def test_hearts_are_per_person(self):
        idea = m.Idea.objects.first()
        self.client.post(reverse("idea_love", args=[idea.pk]))
        idea.refresh_from_db()
        self.assertTrue(idea.loved_by_denver)
        self.assertFalse(idea.loved_by_richard)

    # -- deleting / search ---------------------------------------------------

    def test_delete(self):
        note = m.Note.objects.first()
        self.client.post(reverse("delete", args=["note", note.pk]))
        self.assertFalse(m.Note.objects.filter(pk=note.pk).exists())

    def test_category_with_items_is_protected(self):
        cat = m.BudgetCategory.objects.filter(items__isnull=False).first()
        resp = self.client.post(reverse("delete", args=["budgetcategory", cat.pk]))
        self.assertIn("planner:error", json.loads(resp["HX-Trigger"]))
        self.assertTrue(m.BudgetCategory.objects.filter(pk=cat.pk).exists())

    def test_search_finds_across_sections(self):
        resp = self.client.get(reverse("search"), {"q": "hermitage"})
        self.assertContains(resp, "Venue")
        self.assertContains(resp, "Task")
        self.assertContains(resp, "Idea")
