# HostPro

Django application for hosting, domain registration, client accounts and billing.

## Local setup

1. Create and activate a Python virtual environment.
2. Install the Python dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set unique local secrets.
4. Leave `DB_ENGINE=sqlite` for local development, then run `python manage.py migrate` and `python manage.py runserver`.
5. Build the production CSS with `npm ci` and `npm run build:css`.

## Production database

Use PostgreSQL for production. Create a database and database user in the hosting control panel, grant that user access to the database, then set `DB_ENGINE=postgresql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_HOST` in the server environment. Back up the existing SQLite database and migrate its data before switching the live application. Do not commit `.env` or paste production credentials into source files or documentation.

Build `static/css/site.css` before deploying templates, then run Django's `collectstatic` step on the server.

## Security notice

Previous revisions of this README contained account credentials. Treat them as exposed: change those passwords and any related credentials, and remove the old values from repository history before sharing the repository.
