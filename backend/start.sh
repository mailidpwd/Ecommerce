#!/bin/bash

# Quick start script for backend API

echo "🚀 Starting Decision Recommendation Backend..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found! Please install Python 3.9+"
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "❌ pip not found! Please install pip"
    exit 1
fi

# Install dependencies if not already installed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

echo "🎭 Installing Playwright browsers..."
playwright install chromium --with-deps

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Starting server on http://localhost:8000"
echo "📚 API docs: http://localhost:8000/docs"
echo ""
echo "⏱️  Performance target: <5 seconds per request"
echo ""

# Start the server
python main.py

