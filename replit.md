# RandomQuiz - Replit Project

## Overview
RandomQuiz is a quiz delivery platform with a Django REST Framework backend and React frontend (Vite + TailwindCSS). Instructors manage problem banks, quizzes, and assignments while students access quizzes via public links.

**Current Status**: Fully configured and running in Replit environment
**Last Updated**: November 16, 2025

## Project Architecture

### Backend (Django)
- **Location**: `backend/`
- **Framework**: Django 4.2.7 + Django REST Framework
- **Database**: SQLite (development) - `backend/db.sqlite3`
- **Port**: localhost:8000
- **Apps**:
  - `accounts`: Instructor profiles with admin permissions
  - `problems`: Problem banks and problems
  - `quizzes`: Quiz management, slots, attempts, and responses
  - `api`: REST API endpoints for instructors and public student flow

### Frontend (React)
- **Location**: `frontend/`
- **Framework**: React 18 + Vite 5
- **Styling**: TailwindCSS
- **Port**: 0.0.0.0:5000 (configured for Replit proxy)
- **Main Pages**:
  - Login page for instructors
  - Dashboard with quiz overview
  - Quiz editor for creating/managing quizzes
  - Problem bank manager
  - Admin instructor manager
  - Public quiz landing and attempt pages

## Recent Changes

### Replit Environment Setup (Nov 16, 2025)
1. Installed Python 3.11 and Node.js 20
2. Configured Vite to run on port 5000 with host 0.0.0.0
3. Updated Django CSRF_TRUSTED_ORIGINS to dynamically include Replit domains from environment variables
4. Created combined startup script (`start_all.sh`) that runs both backend and frontend for development
5. Set up workflow to run the application in development mode
6. Configured deployment for autoscale target with production servers

### Production Deployment Setup (Nov 16, 2025)
1. Added WhiteNoise for efficient static file serving
2. Added gunicorn as production WSGI server
3. Configured Django to serve built React frontend from `frontend/dist/`
4. Created custom view to serve React app for client-side routing
5. Made DEBUG, SECRET_KEY configurable via environment variables
6. Deployment build command: `cd frontend && npm install && npm run build`
7. Deployment run command: `cd backend && python manage.py migrate && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 randomquiz.wsgi:application`

### Environment Variables
- `DEBUG`: Set to 'False' in production (defaults to 'True' in development)
- `SECRET_KEY`: Production secret key (defaults to 'dev-secret-key' in development)
- `PORT`: Server port (automatically set by Replit in production, defaults to 5000)
- `REPL_SLUG`, `REPL_OWNER`, `REPLIT_DEV_DOMAIN`: Used to build CSRF trusted origins for Replit domains

### Configuration Details
- **Vite Config**: Set to host on 0.0.0.0:5000 with proxy for `/api` to localhost:8000 (development)
- **Django Settings**: 
  - CORS enabled with CORS_ALLOW_ALL_ORIGINS = True
  - CSRF trusted origins dynamically built from REPL_SLUG, REPL_OWNER, and REPLIT_DEV_DOMAIN environment variables
  - Covers localhost development and all Replit deployment domains (repl.co, replit.dev, replit.app)
  - WhiteNoise middleware configured for static file serving in production
  - STATICFILES_DIRS points to `frontend/dist/assets/` for CSS/JS files
  - WHITENOISE_ROOT points to `frontend/dist/` for serving the React app
- **Database**: Migrations run, ready for use (superuser needs to be created)

## Running the Application

### Development (Automatic)
The application starts automatically via the configured workflow which runs `start_all.sh`:
1. Django backend starts on localhost:8000
2. Vite frontend starts on 0.0.0.0:5000
3. Frontend proxies API requests to backend

### Manual Start (if needed)
```bash
./start_all.sh
```

### Creating a Superuser
To create an initial admin instructor:
```bash
cd backend
python manage.py createsuperuser
```

## Key Files

- `start_all.sh` - Combined startup script for both servers
- `backend/randomquiz/settings.py` - Django configuration
- `frontend/vite.config.js` - Vite configuration with port and proxy settings
- `backend/db.sqlite3` - SQLite database (gitignored)
- `.gitignore` - Excludes node_modules, __pycache__, db.sqlite3, etc.

## API Endpoints

### Authentication
- `POST /api/auth/login/` - Instructor login
- `POST /api/auth/logout/` - Logout

### Instructor Endpoints (Authenticated)
- `/api/problem-banks/` - Manage problem banks
- `/api/problems/` - Manage problems
- `/api/quizzes/` - Manage quizzes
- `/api/quizzes/<id>/slots/` - Quiz slots
- `/api/quizzes/<id>/allowed-instructors/` - Quiz permissions

### Public Student Endpoints
- `GET /api/public/quizzes/<public_id>/` - Quiz landing page info
- `POST /api/public/quizzes/<public_id>/start/` - Start quiz attempt
- `POST /api/public/attempts/<attempt_id>/slots/<slot_id>/answer/` - Submit answer
- `POST /api/public/attempts/<attempt_id>/complete/` - Complete quiz

## Dependencies

### Python (requirements.txt)
- Django==4.2.7
- djangorestframework==3.14.0
- django-cors-headers==4.3.1

### Node.js (frontend/package.json)
- react, react-dom, react-router-dom
- axios (API client)
- vite (build tool)
- tailwindcss (styling)
- marked, dompurify (markdown rendering)

## User Preferences
None specified yet.

## Next Steps
1. Create a superuser account for initial access
2. Add sample problem banks and quizzes
3. Test the public quiz flow
4. Consider production deployment with proper SECRET_KEY and database
