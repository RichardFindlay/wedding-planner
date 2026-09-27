# Richard & Denver — wedding planner

Our private planning site for **Saturday 29 May 2027** (provisional): tasks, budget scenarios, venues and enquiries, guests, ideas, suppliers, travel, timeline and decisions, all in one place.

Built with Django, plus [htmx](https://htmx.org) so edits save as soon as you make them, with no separate edit pages.

## Running it locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py setup_wedding   # creates Richard & Denver, loads the starter plan
.venv/bin/python manage.py runserver
```

Open http://localhost:8000 and pick who you are. Locally it uses SQLite (`db.sqlite3`).

Run the tests with `.venv/bin/python manage.py test planner`.

## Deploying on Railway

1. In the Railway project, add a **Postgres** database.
2. On the web service, set these variables:
   - `DATABASE_URL` → reference the Postgres service's `DATABASE_URL`
   - `SECRET_KEY` → any long random string
3. Deploy from this repo. `railway.json` runs `start.sh`, which migrates, collects static files, sets up the two of us (and the starter plan on first run only), then starts gunicorn.
4. Under **Settings → Networking**, generate a public domain.

Uploaded photos are stored in Postgres, so nothing is lost between deploys.

> **Note:** there are no passwords. Anyone with the link can view and edit, so don't share it. Pages are marked `noindex`, so search engines shouldn't list the site.

## How it's put together

| Where | What |
|---|---|
| `planner/models.py` | Everything we track. Estimates and confirmed quotes are always separate fields. |
| `planner/registry.py` | For each record type, which fields appear in "+ Add" and in the edit drawer |
| `planner/views.py` | Pages, plus generic endpoints: `field_update` (autosave one field), `create`, `delete`, `drawer` |
| `planner/templatetags/planner_tags.py` | `{% edit obj "field" %}` renders a control that saves itself |
| `planner/templates/planner/oob/` | Extra page parts to refresh after an edit (e.g. budget totals) |
| `planner/seed.py` | The starter plan, taken from our brief |

**Logging an enquiry** moves a venue or supplier along. "Enquiry sent" sets the status to *Awaiting Reply* and adds a follow-up a week later. "Reply received" sets it to *Replied* and clears the follow-up.

**Budget**: each line counts the *booked cost* if there is one, otherwise the *quote*, otherwise the *estimate*. The Low / Medium / Higher scenario sets the target and the per-category allowances.
