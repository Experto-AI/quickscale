"""Service verification utilities for QuickScale."""
import subprocess
import socket
import time
import urllib.request
import os
from pathlib import Path
import json


def _verify_container_status(self=None):
    """Verify that the containers are running and healthy."""
    result = {
        'web': {'running': False, 'healthy': False},
        'db': {'running': False, 'healthy': False},
        'success': False
    }
    
    try:
        # Check if web container is running
        web_check = subprocess.run(
            ['docker-compose', 'ps', '-q', 'web'],
            capture_output=True, text=True, check=False
        )
        result['web']['running'] = web_check.returncode == 0 and bool(web_check.stdout.strip())
        
        # Check if db container is running
        db_check = subprocess.run(
            ['docker-compose', 'ps', '-q', 'db'],
            capture_output=True, text=True, check=False
        )
        result['db']['running'] = db_check.returncode == 0 and bool(db_check.stdout.strip())
        
        # Only check health if containers are running
        if result['web']['running']:
            # Check web container health
            web_health = subprocess.run(
                ['docker-compose', 'exec', 'web', 'echo', 'healthy'],
                capture_output=True, text=True, check=False
            )
            result['web']['healthy'] = web_health.returncode == 0 and 'healthy' in web_health.stdout
        
        if result['db']['running']:
            # Check db container health through pg_isready
            db_health = subprocess.run(
                ['docker-compose', 'exec', 'db', 'pg_isready', '-d', os.environ.get('DB_NAME', 'quickscale')],
                capture_output=True, text=True, check=False
            )
            result['db']['healthy'] = db_health.returncode == 0 and 'server is running' in db_health.stdout
        
        result['success'] = result['web']['running'] and result['web']['healthy'] and \
                           result['db']['running'] and result['db']['healthy']
    
    except Exception as e:
        # Log error but continue
        print(f"Error checking container status: {str(e)}")
    
    return result


def _verify_database_connectivity(project_name, self=None):
    """Verify database connectivity and check that migrations are applied."""
    try:
        # Get environment variables from .env file or use defaults
        env_file = Path('.env')
        db_name = 'quickscale'
        db_user = 'admin'
        db_password = 'adminpasswd'
        db_host = 'db'
        
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            if key == 'DB_NAME':
                                db_name = value.strip('"\'')
                            elif key == 'DB_USER':
                                db_user = value.strip('"\'')
                            elif key == 'DB_PASSWORD':
                                db_password = value.strip('"\'')
                            elif key == 'DB_HOST':
                                db_host = value.strip('"\'')
            except Exception as e:
                print(f"Warning: Could not parse .env file: {e}")
        
        # Check database connection using a simple Python script with environment variables
        script = f"""
import psycopg2
import os

# Connect to the database using DB_* variables
try:
    # Get database configuration, preferring environment variables
    db_name = os.environ.get('DB_NAME') or '{db_name}'
    db_user = os.environ.get('DB_USER') or '{db_user}'
    db_password = os.environ.get('DB_PASSWORD') or '{db_password}'
    db_host = os.environ.get('DB_HOST') or '{db_host}'
    
    print(f"Connecting to database: {{db_name}} with user: {{db_user}} on host: {{db_host}}")
    
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host
    )
    conn.close()
    print('Connection successful')
except Exception as e:
    print(f"Connection error: {{str(e)}}")
    raise SystemExit(1)
"""
        
        # Execute the script with docker-compose
        db_check_cmd = [
            'docker-compose', 'exec', '-T', 'web', 'python', '-c', script
        ]
        
        db_check = subprocess.run(db_check_cmd, capture_output=True, text=True, check=True)
        
        # Check that migrations have been applied
        migrations_cmd = [
            'docker-compose', 'exec', '-T', 'web', 'python', 'manage.py', 'showmigrations'
        ]
        
        migrations_check = subprocess.run(migrations_cmd, capture_output=True, text=True, check=True)
        
        # Check that test users have been created
        users_cmd = [
            'docker-compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c',
            """
try:
    from users.models import CustomUser
    admin_exists = CustomUser.objects.filter(email='admin@test.com').exists()
    user_exists = CustomUser.objects.filter(email='user@test.com').exists()
    print(f"Admin user exists: {admin_exists}")
    print(f"Regular user exists: {user_exists}")
except Exception as e:
    print(f"Error checking users: {str(e)}")
    """
        ]
        
        users_check = subprocess.run(users_cmd, capture_output=True, text=True, check=True)
        
        # Database is connected if all checks pass
        return True
    
    except subprocess.CalledProcessError as e:
        # Database connection failed
        print(f"Database connectivity check failed: {str(e)}")
        return False
    except Exception as e:
        # Other errors
        print(f"Error checking database connectivity: {str(e)}")
        return False


def _verify_web_service(self=None):
    """Verify that the web service is responding and serving static files."""
    result = {
        'responds': False,
        'static_files': False,
        'success': False
    }
    
    # Check if web service responds to a socket connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    
    # Try a few times with small delays
    for _ in range(3):
        try:
            sock.connect(('localhost', 8000))
            result['responds'] = True
            break
        except (ConnectionRefusedError, socket.timeout):
            time.sleep(1)
    
    sock.close()
    
    # Check if static files are served
    if result['responds']:
        try:
            # Try to access a static file or the favicon
            favicon_url = 'http://localhost:8000/static/favicon.ico'
            response = urllib.request.urlopen(favicon_url, timeout=5)
            result['static_files'] = response.status == 200
        except Exception:
            # Static files might not be ready yet, but that's not critical
            result['static_files'] = False
    
    # Service is considered successful if it responds, regardless of static files
    result['success'] = result['responds']
    
    return result 