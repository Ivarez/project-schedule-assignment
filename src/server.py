"""Servidor web local (sin dependencias externas) para la interfaz visual del proyecto.

Ejecución:
    python -m src.server
o:
    python run_app.py
"""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

from .data_manager import (
    ensure_default_scenarios,
    generate_instance,
    load_instance,
    validate_instance_consistency,
)
from .models import Instance, Weights
from .solver import run_all_solvers

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
WEB_ROOT = PROJECT_ROOT / "web"

# Caché en memoria de instancias cargadas o generadas al vuelo
_INSTANCES: Dict[str, Instance] = {}


def _load_all_scenarios() -> None:
    paths = ensure_default_scenarios(DATA_ROOT)
    for key, folder in paths.items():
        _INSTANCES[key] = load_instance(folder)


def _serialize_instance_summary(inst: Instance) -> dict:
    return {
        "name": inst.name,
        "description": inst.description,
        "seed": inst.seed,
        "stats": {
            "students": len(inst.students),
            "courses": len(inst.courses),
            "sections": len(inst.sections),
            "time_slots": len(inst.time_slots),
            "buildings": len(inst.locations.buildings),
            "social_links": len(inst.social_links),
            "total_requests": sum(len(s.requested_courses) for s in inst.students.values()),
        },
        "default_weights": inst.default_weights.to_dict(),
    }


def _serialize_instance_full(inst: Instance) -> dict:
    return {
        **_serialize_instance_summary(inst),
        "time_slots": {tid: ts.to_dict() for tid, ts in inst.time_slots.items()},
        "locations": inst.locations.to_dict(),
        "courses": {cid: c.to_dict() for cid, c in inst.courses.items()},
        "sections": {sid: s.to_dict() for sid, s in inst.sections.items()},
        "students": {eid: st.to_dict() for eid, st in inst.students.items()},
        "social_links": [lk.to_dict() for lk in inst.social_links],
    }


class ScheduleRequestHandler(BaseHTTPRequestHandler):
    """Manejador HTTP para archivos estáticos y endpoints JSON del solver."""

    def log_message(self, format: str, *args) -> None:
        # Log compacto y limpio en consola
        print(f"[HTTP] {self.address_string()} - {format % args}")

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _serve_static(self, rel_path: str) -> None:
        clean = "index.html" if rel_path in ("", "/") else rel_path.lstrip("/")
        file_path = (WEB_ROOT / clean).resolve()
        if not str(file_path).startswith(str(WEB_ROOT.resolve())) or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Archivo no encontrado")
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scenarios":
            items = [_serialize_instance_summary(inst) for inst in _INSTANCES.values()]
            self._send_json({"scenarios": items})
            return

        if parsed.path.startswith("/api/scenario/"):
            key = parsed.path.split("/api/scenario/", 1)[1]
            inst = _INSTANCES.get(key)
            if inst is None:
                self._send_json({"error": f"Escenario '{key}' no encontrado"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"instance": _serialize_instance_full(inst)})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "JSON inválido"}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/solve":
            key = payload.get("scenario", "pequeno")
            inst = _INSTANCES.get(key)
            if inst is None:
                self._send_json({"error": f"Escenario '{key}' no encontrado"}, HTTPStatus.NOT_FOUND)
                return
            weights = Weights.from_dict(payload.get("weights", {}))
            include_exact = bool(payload.get("include_exact", len(inst.students) <= 10))
            exact_limit = float(payload.get("exact_time_limit", 2.0))
            results = run_all_solvers(
                inst,
                weights=weights,
                include_exact=include_exact,
                exact_time_limit=min(max(exact_limit, 0.3), 5.0),
            )
            self._send_json({
                "scenario": key,
                "weights": weights.to_dict(),
                "results": {k: v.to_dict() for k, v in results.items()},
            })
            return

        if parsed.path == "/api/generate":
            n_st = max(4, min(200, int(payload.get("num_students", 20))))
            n_co = max(3, min(25, int(payload.get("num_courses", 10))))
            seed = int(payload.get("seed", 777))
            stress = bool(payload.get("stress_conflicts", False))
            key = f"custom_{seed}_{n_st}e_{n_co}m"
            inst = generate_instance(
                name=key,
                description=f"Escenario personalizado ({n_st} estudiantes, {n_co} materias, semilla {seed}).",
                num_students=n_st,
                num_courses=n_co,
                sections_per_course=(2, 3 if n_st <= 40 else 4),
                courses_per_student=(3, min(5, n_co)),
                capacity_range=(max(3, n_st // 6), max(6, n_st // 3)),
                social_density=0.25 if n_st <= 40 else 0.12,
                seed=seed,
                stress_conflicts=stress,
            )
            ok, errs = validate_instance_consistency(inst)
            if not ok:
                self._send_json({"error": "Instancia inválida", "details": errs}, HTTPStatus.BAD_REQUEST)
                return
            _INSTANCES[key] = inst
            self._send_json({"instance": _serialize_instance_full(inst)})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint no encontrado")


def start_server(host: str = "127.0.0.1", port: int = 8080, open_browser: bool = True) -> None:
    """Inicializa los escenarios y arranca el servidor HTTP local."""
    _load_all_scenarios()
    server = ThreadingHTTPServer((host, port), ScheduleRequestHandler)
    url = f"http://{host}:{port}"
    print(f"============================================================")
    print(f"  PUJ · Asignación de Horarios Estudiantiles (Interfaz Web)")
    print(f"  Servidor activo en: {url}")
    print(f"  Escenarios cargados: {', '.join(_INSTANCES.keys())}")
    print(f"  Presiona Ctrl+C para detener.")
    print(f"============================================================")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido correctamente.")
    finally:
        server.server_close()


if __name__ == "__main__":
    start_server()
