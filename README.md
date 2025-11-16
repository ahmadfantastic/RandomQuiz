# RandomQuiz

RandomQuiz is a reference implementation of a quiz delivery platform. The backend is a Django + Django REST Framework API using SQLite by default. The frontend is a React single-page app built with Vite and TailwindCSS. Instructors manage problem banks, quizzes, slots, and assignments; students start quizzes via public links and submit answers.

**Repository layout (top-level)**

- `backend/` — Django project and apps (`accounts`, `problems`, `quizzes`, `api`).
- `frontend/` — React SPA (Vite + TailwindCSS).
- `requirements.txt` — Python dependencies for the backend.
- `package.json` — frontend dependencies and dev scripts.

**Key backend apps**

- `accounts`: Instructor profile wrapper around Django users with `is_admin_instructor`.
- `problems`: Problem banks and ordered problems (problems do not have titles; display labels are positional).
- `quizzes`: Quiz, slot, slot-problem join records, quiz attempts and assigned problems.
- `api`: DRF viewsets and public endpoints used by the frontend and by anonymous quiz takers.

Requirements

- Backend (from `requirements.txt`): `Django==4.2.7`, `djangorestframework==3.14.0`, `django-cors-headers==4.3.1`.
- Frontend (selected `package.json` deps): `react`, `react-dom`, `react-router-dom`, `axios`, `marked`, `dompurify`, `tailwindcss`, `vite`.

Quick start (development)

1) Backend (run in one terminal)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r ../requirements.txt
python3 manage.py migrate
python3 manage.py createsuperuser  # create an initial admin instructor
python3 manage.py runserver
```

2) Frontend (run in another terminal)

```bash
cd frontend
npm install
npx vite          # or `npm run dev`
```

## Environment configuration

- Copy `.env.example` to `.env` at the project root and update any values you need. The backend loads this file with `python-dotenv`, falling back to sqlite if no database engine credentials are supplied.
- Use `DJANGO_DB_ENGINE=mysql` or `postgresql` plus the accompanying `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, and `DJANGO_DB_PORT` values to switch the backend to those engines; otherwise it continues to use the default sqlite store.

Notes about running locally

- The frontend dev server (Vite) is configured to proxy `/api/*` requests to the Django backend so you can run both services concurrently without extra CORS configuration. The Django settings in `backend/randomquiz/settings.py` also enable CORS for development (`CORS_ALLOW_ALL_ORIGINS = True`) and list `http://localhost:5173` in `CSRF_TRUSTED_ORIGINS`.
- Backend REST framework defaults to session/basic authentication and `IsAuthenticated` by default; the `api` app exposes both authenticated instructor endpoints and public endpoints (prefixed with `/api/public/`) used by students.
- When building for production, run `npm run build` in `frontend/` and serve the built assets from a suitable static host or integrate them with a production Django static setup.

Important API endpoints (prefix: `/api/`)

- Auth: `auth/login/`, `auth/logout/` (backend session login used by the SPA).
- Problem banks and problems: `problem-banks/`, `problems/`, nested `problem-banks/<id>/problems/`.
- Quizzes: `quizzes/`, `quizzes/<id>/slots/`, `slots/<id>/slot-problems/`, `quizzes/<id>/allowed-instructors/`.
- Public student flow: `public/quizzes/<public_id>/` (quiz landing), `public/quizzes/<public_id>/start/` (create attempt/assign problems), `public/attempts/<attempt_id>/slots/<slot_id>/answer/` (submit slot answer), `public/attempts/<attempt_id>/complete/` (finish attempt).

Frontend overview

- Built with React + Vite. TailwindCSS for styling.
- Main pages/components (in `frontend/src/pages`):
	- `LoginPage` — instructor login.
	- `DashboardPage` — overview and quiz list.
	- `QuizEditorPage` — create/edit quiz metadata and slots.
	- `ProblemBankManager` — manage banks and problems.
	- `AdminInstructorManager` — create/manage instructor accounts.
	- Public flow pages: `PublicQuizLandingPage`, `QuizAttemptPage`, `ThankYouPage`.

Development tips

- If the frontend dev server cannot reach the API, verify the backend is running at `http://127.0.0.1:8000` and that the Vite proxy is enabled (check `frontend/vite.config.js`).
- CSRF: the SPA uses session authentication for instructor flows. `CSRF_TRUSTED_ORIGINS` includes `http://localhost:5173` in `backend/randomquiz/settings.py`.
- To reset the database quickly: stop the server, delete `backend/db.sqlite3`, then run `python3 manage.py migrate` and recreate a superuser.

Testing and further work

- There are no automated test runners included in this repo by default. You can add Django unit tests in the `backend/` apps and run them with `python3 manage.py test`.
- To prepare this project for production, add a production-ready `SECRET_KEY`, set `DEBUG=False`, and configure a production database and static-file hosting.

Contact / Next steps

- If you'd like, I can: run the dev servers and verify the public quiz flow, add example data fixtures, or add a CONTRIBUTING or deployment guide. Tell me which you prefer.
