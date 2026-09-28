# AddressBook V7.9.0

A multi-user contact manager: a **Kivy** mobile/desktop app talking to a **Django REST** backend
(JWT auth) that stores data in **PostgreSQL** (hosted on Render).
The app never holds database credentials, so an APK built from it exposes no secrets.

```
AddressBook-V7/
├── addressbook_backend/   Django + DRF + PostgreSQL  (deploy to Render)
└── addressbook_app/       Kivy client                (desktop now, APK later)
```

## 1. Backend

```bash
cd addressbook_backend
pip install -r requirements.txt
cp .env.example .env        # fill in your Render PostgreSQL values + a secret key
python manage.py migrate
python manage.py runserver
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Deploy on Render (Web Service)
- Build command: `pip install -r requirements.txt && python manage.py migrate`
- Start command: `gunicorn addressbook_backend.wsgi`
- Environment variables: everything in `.env.example`
  (`DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=<your-service>.onrender.com`)

### API
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register/` | create account |
| POST | `/api/auth/login/` | returns `access` + `refresh` tokens |
| POST | `/api/auth/refresh/` | new access token |
| GET | `/api/auth/me/` | current user |
| DELETE | `/api/auth/delete/` | delete account + its contacts |
| GET/POST | `/api/contacts/` | list / create |
| GET/PUT/DELETE | `/api/contacts/{id}/` | read / update / delete |
| GET | `/api/contacts/search/?q=` | search name / phone / email |

## 2. App

```bash
cd addressbook_app
pip install -r requirements.txt
# edit config.py -> API_BASE_URL (local server or your Render URL)
python main.py
```
