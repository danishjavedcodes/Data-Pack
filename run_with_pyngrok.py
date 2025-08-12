#!/usr/bin/env python3
"""
Run Streamlit app with pyngrok tunnel for public access.
Alternative to run_with_ngrok.py - uses Python library instead of CLI.
"""

import subprocess
import time
import sys
import os
import threading
from pathlib import Path

try:
    from pyngrok import ngrok
    from pyngrok.conf import PyngrokConfig
except ImportError:
    print("❌ pyngrok not installed. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
    from pyngrok import ngrok
    from pyngrok.conf import PyngrokConfig

# Configuration
NGROK_TOKEN = "2vrA8dm5jYCtzHdPi6Io5uZXjml_4vgLkEUHTHwQRrnPQQEY8"
STREAMLIT_PORT = 8501

def start_streamlit():
    """Start Streamlit app in background."""
    try:
        # Set environment variables for ngrok compatibility
        env = os.environ.copy()
        env.update({
            'STREAMLIT_SERVER_PORT': str(STREAMLIT_PORT),
            'STREAMLIT_SERVER_ADDRESS': 'localhost',
            'STREAMLIT_SERVER_HEADLESS': 'true',
            'STREAMLIT_BROWSER_GATHER_USAGE_STATS': 'false',
            'NGROK_TUNNEL': 'true'  # Flag for the app
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

def setup_ngrok():
    """Setup ngrok with auth token."""
    try:
        # Configure ngrok
        config = PyngrokConfig(auth_token=NGROK_TOKEN)
        ngrok.set_auth_token(NGROK_TOKEN)
        print("✅ ngrok configured with auth token")
        return True
    except Exception as e:
        print(f"❌ Failed to configure ngrok: {e}")
        return False

def start_ngrok_tunnel():
    """Start ngrok tunnel and return the public URL."""
    try:
        # Start tunnel
        tunnel = ngrok.connect(STREAMLIT_PORT, "http")
        public_url = tunnel.public_url
        
        print(f"✅ ngrok tunnel established")
        print(f"   Local: http://localhost:{STREAMLIT_PORT}")
        print(f"   Public: {public_url}")
        
        return tunnel
    except Exception as e:
        print(f"❌ Failed to start ngrok tunnel: {e}")
        return None

def main():
    """Main function to run Streamlit with pyngrok."""
    print("🚀 Starting TARUMResearch Dataset Builder with pyngrok tunnel...")
    print("=" * 60)
    
    # Setup ngrok
    if not setup_ngrok():
        return
    
    # Start Streamlit
    streamlit_process = start_streamlit()
    if not streamlit_process:
        return
    
    # Wait for Streamlit to start
    print("⏳ Waiting for Streamlit to start...")
    time.sleep(5)
    
    # Start ngrok tunnel
    tunnel = start_ngrok_tunnel()
    if not tunnel:
        streamlit_process.terminate()
        return
    
    print("\n" + "=" * 60)
    print("🎉 Your app is now accessible at:")
    print(f"   🌐 {tunnel.public_url}")
    print("=" * 60)
    print("\n📝 Notes:")
    print("   • The URL will change each time you restart")
    print("   • Keep this terminal open to maintain the tunnel")
    print("   • Press Ctrl+C to stop both Streamlit and ngrok")
    print("   • Local access: http://localhost:8501")
    
    try:
        # Keep the main process running
        while True:
            time.sleep(1)
            # Check if Streamlit is still running
            if streamlit_process.poll() is not None:
                print("❌ Streamlit process stopped unexpectedly")
                break
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        # Cleanup
        if tunnel:
            ngrok.disconnect(tunnel.public_url)
            print("✅ ngrok tunnel stopped")
        if streamlit_process:
            streamlit_process.terminate()
            print("✅ Streamlit stopped")
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()
