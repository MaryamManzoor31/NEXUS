"""Entry point for NEXUS Web UI.
Run:
    python web_app.py
Then open http://127.0.0.1:5001 in your browser.
"""
from web.server import app

if __name__ == "__main__":
    print("\n=======================================================")
    print("  NEXUS AI-Assisted Timetable Generator Web App")
    print("  Running at: http://127.0.0.1:5001")
    print("  Press Ctrl+C to stop the server")
    print("=======================================================\n")
    app.run(host="127.0.0.1", port=5002, debug=False, use_reloader=False)
