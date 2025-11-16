#!/bin/bash

# Start Django backend on localhost:8000 in background
cd backend
python manage.py runserver localhost:8000 &
BACKEND_PID=$!
cd ..

# Start Vite frontend on 0.0.0.0:5000 in foreground
cd frontend
npm run dev

# Kill backend when frontend stops
kill $BACKEND_PID 2>/dev/null
