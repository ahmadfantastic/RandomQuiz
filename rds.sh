#!/bin/bash

# Function to kill all background processes on exit
cleanup() {
    echo "Stopping all processes..."
    # Kill all child processes of this script
    pkill -P $$
    exit
}

trap cleanup SIGINT SIGTERM EXIT

# Start Backend
echo "Starting Backend..."
(
    cd backend || exit
    # activate venv if it exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    # Install dependencies and migrate
    pip3 install -r requirements.txt
    python3 manage.py makemigrations
    python3 manage.py migrate
    # Run server
    python3 manage.py runserver
) &

# Start Frontend
echo "Starting Frontend..."
(
    cd frontend || exit
    npm install
    npm run dev
) &

# Wait for all background processes
wait