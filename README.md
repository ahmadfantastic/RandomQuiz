# RandomQuiz

RandomQuiz is a reference implementation of the quiz deployment stack described in the prompt. The backend is built with Django + Django REST Framework + SQLite and the frontend is a React SPA. Students start quizzes via public links and instructors manage problem banks, quizzes, slots, and assignments.

## Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r ../requirements.txt
python3 manage.py migrate
python3 manage.py createsuperuser  # create an initial admin instructor
python3 manage.py runserver
```

Key apps:

- `accounts`: wraps Django users in Instructor profiles with an `is_admin_instructor` flag.
- `problems`: stores problem banks and ordered problems without titles.
- `quizzes`: models quizzes, slots, allowed problems (via `QuizSlotProblemBank`), and student attempts.
- `api`: DRF viewsets and public endpoints, including student quiz start/answer/complete flows.

Important endpoints (all prefixed by `/api/`):

- `auth/login/`, `auth/logout/`
- CRUD for `problem-banks/`, `problems/`, nested `problem-banks/<id>/problems/`
- `quizzes/` plus `quizzes/<id>/slots/`, `slots/<id>/slot-problems/`, `quizzes/<id>/allowed-instructors/`
- Public: `public/quizzes/<public_id>/`, `public/quizzes/<public_id>/start/`, `public/attempts/<attempt_id>/slots/<slot_id>/answer/`, `public/attempts/<attempt_id>/complete/`

## Frontend setup

```bash
cd frontend
npm install
npm start
```

Pages include instructor login, dashboard, quiz editor, slot manager, problem bank manager, admin instructor tools, and the student public quiz/attempt/thank-you flow. The SPA consumes the `/api/` endpoints above; enable CORS or run the frontend on the same origin during development.

## Example workflow

1. Create an admin instructor via `createsuperuser`, log into `/admin/`, ensure the Instructor profile has `is_admin_instructor=True`.
2. Call `/api/auth/login/` or use the React login page, then create problem banks such as PAP and PBP.
3. Populate each bank with ordered problems (`order_in_bank` = 1..20).
4. Create the “Fall 2025 Quiz” with `public_id` (e.g., `fall-2025`), start/end times, and description.
5. Add three slots, each pointing to the appropriate problem bank. Use the slot manager to attach allowed problems per slot via the `QuizSlotProblemBank` join records.
6. Share the public link `/q/fall-2025`. Students enter identifiers and receive randomized problems per slot. Answers and completion timestamps are stored in `QuizAttempt`/`QuizAttemptSlot`.

## Notes

- Problems never have titles. Display labels derive from the order within the original bank (e.g., “Problem 3”).
- The random selection occurs once per attempt and is persisted in `QuizAttemptSlot.assigned_problem`.
- SQLite is the default database, but the ORM models are portable to other engines.
- This repo does not ship compiled assets; run `npm start` for the development server and `python manage.py runserver` for the API.
