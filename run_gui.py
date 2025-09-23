import webview
import threading
import app

def start_flask():
    app.app.run(debug=False, port=8000)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()
    # Wait a moment for Flask to start
    import time; time.sleep(1)
    webview.create_window('AIC Flight Deck', 'http://127.0.0.1:8000', height=900)
    webview.start()
