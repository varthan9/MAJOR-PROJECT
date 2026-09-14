# Fruit Monitoring Backend

Run with Python 3.10+:

```powershell
python backend/server.py
```

The server hosts the dashboard at `http://localhost:8000` and exposes mock REST data under `/api`. The logistics score combines demand/capacity and distance; the negotiator selects the nearest available vehicle as a simplified Contract Net decision.

## IoT sensor API

The backend stores device readings in `backend/fruit_monitor.db` using SQLite. An ESP32 gateway, MQTT subscriber, or test script can send JSON to:

```text
POST /api/iot/sensor
Content-Type: application/json
```

Example payload:

```json
{
	"device_id": "ESP32-01",
	"fruit_id": "F001",
	"temperature": 27.1,
	"humidity": 65.4,
	"pressure": 1008.2,
	"gas_resistance": 95321,
	"recorded_at": "2026-09-15T10:42:00Z"
}
```

The response is `201 Created`. Stored data can be read with `GET /api/sensors/latest` and `GET /api/sensors/history`. In a production deployment, place the API behind HTTPS and authenticate devices with per-device credentials or certificates; do not expose this development server directly to the public internet.