#!/usr/bin/env python
"""
Utility script to help with testing Docker container readiness.
This script makes several attempts to connect to the web service and provides detailed debugging
information if the connection fails.
"""
import argparse
import socket
import subprocess
import sys
import time


def is_port_open(host, port, timeout=5):
    """Check if a port is open on the given host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            return result == 0
    except socket.error as e:
        print(f"Socket error when checking {host}:{port} - {e}")
        return False

def check_container_logs(container_name):
    """Check logs of a container for errors."""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', '30', container_name],
            capture_output=True, text=True, check=False
        )
        return result.stdout, result.stderr
    except Exception as e:
        return f"Error getting logs: {e}", ""

def wait_for_service(host, port, container_name, max_attempts=10, delay=5):
    """Wait for a service to become available on a specific port."""
    print(f"Waiting for service at {host}:{port} (container: {container_name})...")
    
    for attempt in range(1, max_attempts + 1):
        print(f"Attempt {attempt}/{max_attempts}...")
        
        if is_port_open(host, port):
            print(f"✅ Service is available at {host}:{port}")
            return True
        
        print(f"⌛ Service not yet available (attempt {attempt}/{max_attempts}).")
        
        # Show container status every other attempt
        if attempt % 2 == 0:
            try:
                ps_result = subprocess.run(
                    ['docker', 'ps', '-a', '--filter', f'name={container_name}'],
                    capture_output=True, text=True, check=False
                )
                print(f"Container status:\n{ps_result.stdout}")
                
                # If we have a specific container name, get its logs
                if container_name and container_name != "":
                    stdout, stderr = check_container_logs(container_name)
                    if stdout:
                        print(f"Recent container logs (stdout):\n{stdout}")
                    if stderr:
                        print(f"Recent container logs (stderr):\n{stderr}")
            except Exception as e:
                print(f"Error checking container status: {e}")
        
        if attempt < max_attempts:
            print(f"⌛ Waiting {delay} seconds before next attempt...")
            time.sleep(delay)
    
    print(f"❌ Service not available at {host}:{port} after {max_attempts} attempts")
    return False

def main():
    parser = argparse.ArgumentParser(description="Wait for a service to be available")
    parser.add_argument("--host", default="localhost", help="Host to connect to")
    parser.add_argument("--port", type=int, required=True, help="Port to connect to")
    parser.add_argument("--container", default="", help="Container name for logs")
    parser.add_argument("--attempts", type=int, default=10, help="Maximum number of attempts")
    parser.add_argument("--delay", type=int, default=5, help="Delay between attempts in seconds")
    
    args = parser.parse_args()
    
    success = wait_for_service(
        args.host, args.port, args.container, 
        max_attempts=args.attempts, delay=args.delay
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
