import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DATABASE = Path(__file__).resolve().parent / "fruit_monitor.db"

prediction = {
    "fruit_id": "F001", "condition": "RIPE", "confidence": 0.87,
    "remaining_shelf_life_days": 3, "temperature": 27.1, "humidity": 65.4,
    "pressure": 1008.2, "gas_resistance": 95321,
    "updated_at": "2026-09-04T10:42:00Z",
}
sensor_history = [
    {"time": "08:00", "temperature": 25.8, "humidity": 61.2, "gas_resistance": 101200},
    {"time": "08:30", "temperature": 26.1, "humidity": 62.5, "gas_resistance": 100100},
    {"time": "09:00", "temperature": 26.4, "humidity": 63.7, "gas_resistance": 98400},
    {"time": "09:30", "temperature": 26.8, "humidity": 64.1, "gas_resistance": 97000},
    {"time": "10:00", "temperature": 26.9, "humidity": 64.9, "gas_resistance": 96100},
    {"time": "10:30", "temperature": 27.1, "humidity": 65.4, "gas_resistance": 95321},
]
prediction_history = [
    {"time": "Today, 10:42", "condition": "RIPE", "confidence": 0.87},
    {"time": "Today, 08:15", "condition": "RIPE", "confidence": 0.82},
    {"time": "Yesterday, 18:00", "condition": "FRESH", "confidence": 0.79},
]
stores = [
    {"id": "S001", "name": "Green Basket · Indiranagar", "short_name": "Green Basket", "latitude": 12.9716, "longitude": 77.5946, "distance_km": 2.8, "capacity": 100, "demand": 42},
    {"id": "S002", "name": "Daily Harvest · Ulsoor", "short_name": "Daily Harvest", "latitude": 12.9750, "longitude": 77.6000, "distance_km": 4.8, "capacity": 150, "demand": 100},
    {"id": "S003", "name": "Orchard Market · Domlur", "short_name": "Orchard Market", "latitude": 12.9601, "longitude": 77.6387, "distance_km": 7.2, "capacity": 180, "demand": 82},
]
vehicles = [
    {"id": "V001", "name": "Vehicle 1", "available": True, "distance_km": 10, "capacity_kg": 80, "eta_minutes": 35},
    {"id": "V002", "name": "Vehicle 2", "available": True, "distance_km": 3, "capacity_kg": 120, "eta_minutes": 18},
    {"id": "V003", "name": "Vehicle 3", "available": False, "distance_km": 1, "capacity_kg": 100, "eta_minutes": None},
]
agents = [
    {"name": "Sensing Agent", "role": "BME688 telemetry", "status": "ONLINE"},
    {"name": "Forecasting Agent", "role": "Condition prediction", "status": "ONLINE"},
    {"name": "Logistics Agent", "role": "Destination scoring", "status": "ONLINE"},
    {"name": "Negotiator Agent", "role": "Vehicle bidding", "status": "ONLINE"},
]

def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                fruit_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                pressure REAL,
                gas_resistance REAL NOT NULL
            )
        """)

def save_sensor_reading(reading):
    recorded_at = reading.get("recorded_at") or datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO sensor_readings
               (device_id, fruit_id, recorded_at, temperature, humidity, pressure, gas_resistance)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (reading["device_id"], reading["fruit_id"], recorded_at,
             reading["temperature"], reading["humidity"], reading.get("pressure"),
             reading["gas_resistance"]),
        )
        return {"id": cursor.lastrowid, **reading, "recorded_at": recorded_at}

def database_sensor_history():
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT device_id, fruit_id, recorded_at, temperature, humidity, pressure, gas_resistance
               FROM sensor_readings ORDER BY id DESC LIMIT 50"""
        ).fetchall()
    return [dict(row) for row in reversed(rows)]

def validate_sensor_reading(body):
    required = ("device_id", "fruit_id", "temperature", "humidity", "gas_resistance")
    missing = [field for field in required if field not in body]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")
    try:
        normalized = dict(body)
        for field in ("temperature", "humidity", "gas_resistance"):
            normalized[field] = float(normalized[field])
        if "pressure" in normalized and normalized["pressure"] is not None:
            normalized["pressure"] = float(normalized["pressure"])
    except (TypeError, ValueError) as error:
        raise ValueError("Sensor numeric fields must contain numbers") from error
    return normalized

def store_score(store):
    return round((store["demand"] / store["capacity"] * 0.55) + (max(0, 1 - store["distance_km"] / 10) * 0.45), 3)

def build_decision(store_id=None):
    ranked = sorted(stores, key=store_score, reverse=True)
    selected = next((store for store in stores if store["id"] == store_id), ranked[0]) if store_id else ranked[0]
    vehicle = min((item for item in vehicles if item["available"]), key=lambda item: item["distance_km"])
    return {"batch_id": prediction["fruit_id"], "priority": "HIGH", "status": "DISPATCH_RECOMMENDED",
            "destination": selected["short_name"], "store_id": selected["id"], "distance_km": selected["distance_km"],
            "vehicle": vehicle["name"], "vehicle_id": vehicle["id"], "route_minutes": round(selected["distance_km"] * 4 + 6),
            "store_scores": [{"store_id": item["id"], "score": store_score(item)} for item in ranked],
            "negotiation": {"status": "COMPLETED", "bids_received": len(vehicles), "selected": vehicle["name"]}}

def api_payload(path, query):
    decision = build_decision(query.get("store_id", [None])[0])
    stored_history = database_sensor_history()
    data = {"/api/overview": {"prediction": prediction, "decision": decision, "agents": agents},
            "/api/sensors/latest": stored_history[-1] if stored_history else prediction,
            "/api/sensors/history": stored_history or sensor_history,
            "/api/predictions/latest": prediction, "/api/predictions/history": prediction_history,
            "/api/stores": stores, "/api/vehicles": vehicles, "/api/logistics/decision": decision,
            "/api/agents": agents}
    return data.get(path)

class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            data = api_payload(parsed.path, parse_qs(parsed.query))
            self.send_json(data if data is not None else {"error": "Not found"}, 200 if data is not None else 404)
            return
        file_path = FRONTEND / ("index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/"))
        if file_path.is_file() and FRONTEND in file_path.parents:
            content_type = {".css": "text/css", ".js": "application/javascript"}.get(file_path.suffix, "text/html")
            body = file_path.read_bytes()
            self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/logistics/recommend", "/api/iot/sensor"):
            self.send_json({"error": "Not found"}, 404); return
        size = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(size) or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "Request body must be valid JSON"}, 400); return
        if path == "/api/iot/sensor":
            try:
                reading = save_sensor_reading(validate_sensor_reading(body))
            except (KeyError, ValueError) as error:
                self.send_json({"error": str(error)}, 400); return
            self.send_json({"message": "Sensor reading stored", "reading": reading}, 201)
            return
        self.send_json(build_decision(body.get("store_id")))

    def log_message(self, *_):
        pass

if __name__ == "__main__":
    initialize_database()
    print("Fruit monitoring dashboard running at http://localhost:8000")
    ThreadingHTTPServer(("localhost", 8000), Handler).serve_forever()