#!/usr/bin/env python3
"""
Run Streamlit app with ngrok tunnel for public access.
"""

import subprocess
import time
import requests
import json
import sys
import os
from pathlib import Path

# ngrok configuration
NGROK_TOKEN = "2vrA8dm5jYCtzHdPi6Io5uZXjml_4vgLkEUHTHwQRrnPQQEY8"
STREAMLIT_PORT = 8501
NGROK_API_URL = "http://localhost:4040/api/tunnels"

def check_ngrok_installed():
    """Check if ngrok is installed and accessible."""
    try:
        result = subprocess.run(['ngrok', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ ngrok found: {result.stdout.strip()}")
            return True
        else:
            print("❌ ngrok not found or not working")
            return False
    except FileNotFoundError:
        print("❌ ngrok not installed. Please install ngrok first:")
        print("   Download from: https://ngrok.com/download")
        print("   Or install via: pip install pyngrok")
        return False

def configure_ngrok():
    """Configure ngrok with the auth token."""
    try:
        subprocess.run(['ngrok', 'config', 'add-authtoken', NGROK_TOKEN], 
                      check=True, capture_output=True)
        print("✅ ngrok configured with auth token")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to configure ngrok: {e}")
        return False

def start_streamlit():
    """Start Streamlit app in background."""
    try:
        # Set environment variables for better ngrok compatibility
        env = os.environ.copy()
        env.update({
            'STREAMLIT_SERVER_PORT': str(STREAMLIT_PORT),
            'STREAMLIT_SERVER_ADDRESS': 'localhost',
            'STREAMLIT_SERVER_HEADLESS': 'true',
            'STREAMLIT_BROWSER_GATHER_USAGE_STATS': 'false'
        })
        
        # Start Streamlit
        process = subprocess.Popen([
            sys.executable, '-m', 'streamlit', 'run', 'app.py',
            '--server.port', str(STREAMLIT_PORT),
            '--server.address', 'localhost',
            '--server.headless', 'true',
            '--browser.gatherUsageStats', 'false'
        ], env=env)
        
        print(f"✅ Streamlit started on port {STREAMLIT_PORT}")
        return process
    except Exception as e:
        print(f"❌ Failed to start Streamlit: {e}")
        return None

def start_ngrok_tunnel():
    """Start ngrok tunnel to Streamlit port."""
    try:
        process = subprocess.Popen([
            'ngrok', 'http', str(STREAMLIT_PORT),
            '--log=stdout'
        ])
        
        print("✅ ngrok tunnel started")
        return process
    except Exception as e:
        print(f"❌ Failed to start ngrok tunnel: {e}")
        return None

def get_ngrok_url():
    """Get the public ngrok URL."""
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(NGROK_API_URL, timeout=5)
            if response.status_code == 200:
                tunnels = response.json()['tunnels']
                for tunnel in tunnels:
                    if tunnel['proto'] == 'https':
                        return tunnel['public_url']
            time.sleep(2)
        except requests.RequestException:
            time.sleep(2)
    
    return None

def main():
    """Main function to run Streamlit with ngrok."""
    print("🚀 Starting TARUMResearch Dataset Builder with ngrok tunnel...")
    print("=" * 60)
    
    # Check ngrok installation
    if not check_ngrok_installed():
        print("\n💡 Alternative: Install pyngrok and use Python-based tunneling")
        print("   pip install pyngrok")
        return
    
    # Configure ngrok
    if not configure_ngrok():
        return
    
    # Start Streamlit
    streamlit_process = start_streamlit()
    if not streamlit_process:
        return
    
    # Wait for Streamlit to start
    print("⏳ Waiting for Streamlit to start...")
    time.sleep(5)
    
    # Start ngrok tunnel
    ngrok_process = start_ngrok_tunnel()
    if not ngrok_process:
        streamlit_process.terminate()
        return
    
    # Wait for ngrok to establish tunnel
    print("⏳ Waiting for ngrok tunnel to establish...")
    time.sleep(3)
    
    # Get public URL
    public_url = get_ngrok_url()
    if public_url:
        print("\n" + "=" * 60)
        print("🎉 Your app is now accessible at:")
        print(f"   🌐 {public_url}")
        print("=" * 60)
        print("\n📝 Notes:")
        print("   • The URL will change each time you restart ngrok")
        print("   • Keep this terminal open to maintain the tunnel")
        print("   • Press Ctrl+C to stop both Streamlit and ngrok")
        print("   • Local access: http://localhost:8501")
    else:
        print("❌ Failed to get ngrok URL")
        streamlit_process.terminate()
        ngrok_process.terminate()
        return
    
    try:
        # Keep the processes running
        while True:
            time.sleep(1)
            # Check if processes are still running
            if streamlit_process.poll() is not None:
                print("❌ Streamlit process stopped unexpectedly")
                break
            if ngrok_process.poll() is not None:
                print("❌ ngrok process stopped unexpectedly")
                break
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        # Cleanup
        if streamlit_process:
            streamlit_process.terminate()
            print("✅ Streamlit stopped")
        if ngrok_process:
            ngrok_process.terminate()
            print("✅ ngrok tunnel stopped")
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()
