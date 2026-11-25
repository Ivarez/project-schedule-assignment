"""Punto de entrada rápido para lanzar la interfaz visual web del proyecto.

Uso:
    python run_app.py
"""

from src.server import start_server

if __name__ == "__main__":
    start_server(host="127.0.0.1", port=8080, open_browser=True)
