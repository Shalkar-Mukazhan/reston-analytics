#!/bin/bash

cd "$(dirname "$0")/backend"

echo "Запуск бэкенда WasteControl..."

# Активация виртуального окружения (если есть)
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
