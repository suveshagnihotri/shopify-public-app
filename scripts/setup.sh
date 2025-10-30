#!/bin/bash

# Shopify Public App Setup Script

set -e

echo "🚀 Setting up Shopify Public App..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️  Creating .env file..."
    cp env.example .env
    echo "📝 Please edit .env file with your configuration"
fi

# Initialize database
echo "🗄️  Initializing database..."
export FLASK_APP=app.py
flask db init || echo "Database already initialized"
flask db migrate -m "Initial migration" || echo "Migration already exists"
flask db upgrade

echo "✅ Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Shopify app credentials"
echo "2. Run 'python app.py' to start the application"
echo "3. Run 'celery -A celery_app worker --loglevel=info' in another terminal for background tasks"
echo ""
echo "For Docker deployment:"
echo "1. Run 'docker-compose up --build'"
