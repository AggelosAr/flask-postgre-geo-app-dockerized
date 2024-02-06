from app import app
import os

from inits.createDb import initDb

if __name__ == "__main__":
    from waitress import serve
    port = os.environ.get("DEFAULT_FLASK_PORT", "8080")  
    port = int(port)

    initDb()
    serve(app, host="0.0.0.0", port=port)
