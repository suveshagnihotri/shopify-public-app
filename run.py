#!/usr/bin/env python3
"""
Application entry point for the Shopify Public App
"""

import os
import sys
from flask_migrate import upgrade
from app import app, db

def create_tables():
    """Create database tables"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

def run_migrations():
    """Run database migrations"""
    with app.app_context():
        try:
            upgrade()
            print("Database migrations completed successfully!")
        except Exception as e:
            print(f"Migration error: {e}")
            sys.exit(1)

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'create-tables':
            create_tables()
        elif command == 'migrate':
            run_migrations()
        elif command == 'worker':
            # Run Celery worker
            os.system('celery -A celery_app worker --loglevel=info')
        elif command == 'beat':
            # Run Celery beat scheduler
            os.system('celery -A celery_app beat --loglevel=info')
        else:
            print(f"Unknown command: {command}")
            print("Available commands: create-tables, migrate, worker, beat")
            sys.exit(1)
    else:
        # Run the Flask app
        app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
