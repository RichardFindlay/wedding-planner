from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("who/", views.who, name="login"),
    path("switch/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("healthz", views.healthz, name="healthz"),

    path("", views.dashboard, name="dashboard"),
    path("tasks/", views.tasks, name="tasks"),
    path("budget/", views.budget, name="budget"),
    path("venues/", views.venues, name="venues"),
    path("venues/<int:pk>/", views.venue_detail, name="venue_detail"),
    path("suppliers/", views.suppliers, name="suppliers"),
    path("suppliers/<int:pk>/", views.supplier_detail, name="supplier_detail"),
    path("enquiries/", views.enquiries, name="enquiries"),
    path("guests/", views.guests, name="guests"),
    path("ideas/", views.ideas, name="ideas"),
    path("ideas/<int:pk>/image/", views.idea_image, name="idea_image"),
    path("ideas/<int:pk>/love/", views.idea_love, name="idea_love"),
    path("travel/", views.travel, name="travel"),
    path("timeline/", views.timeline, name="timeline"),
    path("decisions/", views.decisions, name="decisions"),
    path("notes/", views.notes, name="notes"),
    path("search/", views.search, name="search"),
    path("images/<int:pk>/", views.image, name="image"),

    path("x/<slug:slug>/new/", views.create, name="create"),
    path("x/<slug:slug>/<int:pk>/", views.drawer, name="drawer"),
    path("x/<slug:slug>/<int:pk>/field/", views.field_update, name="field_update"),
    path("x/<slug:slug>/<int:pk>/delete/", views.delete, name="delete"),
]
