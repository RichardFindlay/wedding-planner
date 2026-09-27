from django.contrib import admin

from . import models as m

admin.site.site_header = "Richard & Denver — wedding planner admin"

for model in (
    m.WeddingSettings, m.Task, m.TimelineItem, m.Venue, m.Supplier, m.Enquiry, m.BudgetCategory,
    m.BudgetItem, m.Guest, m.Idea, m.TravelOption, m.Decision, m.Note,
):
    admin.site.register(model)
