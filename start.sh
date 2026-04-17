#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Запуск WasteControl..."

# Бэкенд
osascript -e "tell application \"Terminal\" to do script \"cd '${ROOT}/backend' && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload\""

# Фронтенд
osascript -e "tell application \"Terminal\" to do script \"cd '${ROOT}/frontend' && npm run dev\""

echo ""
echo "======================================="
echo "  Бэкенд:   http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo "  Фронтенд:  http://localhost:5173"
echo "======================================="
