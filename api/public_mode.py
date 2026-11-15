"""Opt-in public read-only ASGI entry point, separate from api.main (#122).

Local entry point and defaults are unchanged. Start with
uvicorn api.public_mode:create_app --factory. No upload or hosting operation is
performed by this module. Full public planning requires separate session storage.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import parse_qs

from starlette.responses import HTMLResponse, JSONResponse

COMPUTE_POSTS = {"/walkback", "/walkback/update", "/guide/return_home", "/guide/rejoin", "/comms/check"}
CREDITS = "NASA/JPL-Caltech · MRO/HiRISE · USGS. Source-specific credits remain with each image and data product."
NOTICE = ('<aside role="note" style="position:fixed;bottom:3px;left:4px;z-index:9999;'
          'background:#10141a;color:#fff;padding:3px 7px;font:11px system-ui;max-width:85vw">'
          'Fixed-plan public demo · NASA/JPL-Caltech / USGS data · '
          '<a href="/public/credits" style="color:#b9deff">Sources and limits</a></aside>').encode()


class PublicMode:
    """Fail-closed write guard and one-computation-at-a-time public demo.

    Identical /plan requests replay an immutable snapshot; other plans are denied.
    Stations and walk logs are never written. Pure computational POST endpoints
    remain available for rehearsal, with graph/habitat settings pinned to the
    frozen plan. This is a shared read-only demo, not per-visitor live planning.
    """
    def __init__(self, app, *, mode="off", snapshot=None, normalize=lambda value: value,
                 max_body_bytes=2_000_000):
        if mode not in ("off", "readonly"):
            raise ValueError("MARTIAN_PUBLIC_MODE must be off or readonly")
        self.app, self.mode, self.normalize = app, mode, normalize
        self.max_body_bytes = max_body_bytes
        self.gate = asyncio.Semaphore(1)
        self.snapshot = json.loads(json.dumps(snapshot)) if snapshot is not None else None
        if mode == "readonly":
            if not self.snapshot or not isinstance(self.snapshot.get("request"), dict):
                raise ValueError("readonly mode needs a saved request/plan snapshot")
            plan = self.snapshot.get("plan", {})
            if plan.get("type") != "FeatureCollection" or plan.get("properties", {}).get("feasible") is not True:
                raise ValueError("readonly snapshot must contain a feasible FeatureCollection")
            self.request = self.normalize(self.snapshot["request"])
            self.digest = hashlib.sha256(json.dumps(self.snapshot, sort_keys=True).encode()).hexdigest()
            self.habitat = self.snapshot["plan"]["properties"].get("habitat", self.request.get("start"))
            if self.habitat is None:
                raise ValueError("readonly snapshot needs a habitat")

    async def _body(self, receive):
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            body.extend(message.get("body", b""))
            if len(body) > self.max_body_bytes:
                raise ValueError("request body exceeds public-demo limit")
            if not message.get("more_body", False):
                value = json.loads(body or b"{}")
                if not isinstance(value, dict):
                    raise ValueError("request body must be an object")
                return value

    def _pin(self, path, payload):
        if path == "/comms/check":
            # Fixed radio geometry avoids unbounded viewshed caches.
            for key, value in {"gap_m": 20., "max_pair_distance_m": 100.,
                               "antenna_height_m": 3., "astronaut_height_m": 1.7}.items():
                if key in payload and payload[key] != value:
                    raise ValueError("radio settings are fixed in the public demo")
            route = payload.get("route")
            if route is not None:
                planned = next(f for f in self.snapshot["plan"]["features"]
                               if f.get("properties", {}).get("kind") == "route")
                if route.get("coordinates") != planned["geometry"]["coordinates"]:
                    raise ValueError("radio route is fixed in the public demo")
        else:
            for key, value in {"max_cell_slope_deg": self.request.get("max_cell_slope_deg", 30.),
                               "human_cost": self.request.get("human_cost", True)}.items():
                if key in payload and payload[key] != value:
                    raise ValueError("graph settings are fixed in the public demo")
                payload[key] = value
        key = "base" if path == "/walkback" else "habitat"
        if payload.get(key) is not None and payload[key] != self.habitat:
            raise ValueError("habitat is fixed in the public demo")
        payload[key] = self.habitat
        return payload

    def _query(self, scope):
        params = parse_qs(scope.get("query_string", b"").decode("utf-8"), keep_blank_values=True)
        for key in ("max_cell_slope_deg",):
            if key in params:
                expected = self.request.get(key, 30.)
                raw = params[key]
                if len(raw) != 1 or expected is None or float(raw[0]) != expected:
                    raise ValueError("graph settings are fixed in the public demo")
        for key, coord in zip(("x", "y"), self.habitat):
            if key in params and (len(params[key]) != 1 or abs(float(params[key][0]) - coord) > .11):
                raise ValueError("habitat is fixed in the public demo")
        if "sol" in params and params["sol"] != ["4711"]:
            raise ValueError("the public demonstration uses sol 4711")

    async def __call__(self, scope, receive, send):
        if self.mode == "off" or scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"].rstrip("/") or "/", scope["method"]

        async def send_public(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []),
                            (b"x-martian-public-mode", b"readonly")]}
            await send(message)

        def deny(detail, status=403):
            return JSONResponse({"detail": detail, "public_mode": "readonly"}, status_code=status)

        if path == "/public/status" and method == "GET":
            return await JSONResponse({"mode": "readonly", "fixed_plan_sha256": self.digest,
                                       "request": self.request, "credits": CREDITS,
                                       "planning": "fixed replay only", "persistent_writes": False})(scope, receive, send_public)
        if path == "/public/credits" and method == "GET":
            return await HTMLResponse('<!doctype html><html lang="en"><title>Data credits</title>'
                                     '<body><h1>Martian Map public demonstration</h1><p>' + CREDITS +
                                     '</p><p>Metabolism, consumption and contingencies are modelled or simulated. '
                                     'This demo replays a fixed plan; it is not operational EVA guidance.</p>'
                                     '<p><a href="/">Planning map</a> · <a href="/3d/">3D</a> · '
                                     '<a href="/guide.html">Tablet guide</a></p></body></html>')(scope, receive, send_public)
        if path == "/plan/last" and method == "GET":
            return await JSONResponse(self.snapshot)(scope, receive, send_public)
        if method not in ("GET", "HEAD", "OPTIONS", "POST") or (method == "POST" and path not in COMPUTE_POSTS | {"/plan"}):
            return await deny("Persistent writes are disabled in this fixed-plan demonstration.")(scope, receive, send_public)
        payload = None
        try:
            if path.startswith(("/layers", "/plan/", "/weather", "/thermal", "/minerals")):
                self._query(scope)
            if method == "POST":
                payload = await self._body(receive)
                if payload is None:
                    return
                if path == "/plan":
                    if self.normalize(payload) != self.request:
                        return await deny("This is a fixed-plan replay. Load /plan/last; new plans are disabled.")(scope, receive, send_public)
                    result = json.loads(json.dumps(self.snapshot["plan"]))
                    result.setdefault("properties", {})["public_mode"] = "readonly"
                    result["properties"]["fixed_plan_sha256"] = self.digest
                    return await JSONResponse(result)(scope, receive, send_public)
                payload = self._pin(path, payload)
        except (ValueError, TypeError, KeyError, AttributeError) as err:
            return await deny(str(err), 400)(scope, receive, send_public)
        if payload is not None:
            body = json.dumps(payload).encode()
            original_receive = receive
            delivered = False

            async def replay_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await original_receive()

            receive = replay_receive
            scope = {**scope, "headers": [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"content-length"]
                     + [(b"content-length", str(len(body)).encode())]}
        computational = method == "POST" or (not path.startswith(("/tiles/", "/vendor/", "/3d/", "/home/"))
                                             and not path.endswith((".html", ".js", ".css", ".ico")) and path != "/")
        # Credit banner is public-only; it does not change any web/ source file.
        start_message, chunks = None, []

        async def annotated_send(message):
            nonlocal start_message
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                if (method == "GET" and message["status"] == 200
                        and b"text/html" in headers.get(b"content-type", b"")
                        and b"content-encoding" not in headers):
                    start_message = message
                    return
            if start_message is not None and message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    content = b"".join(chunks)
                    content = content.replace(b"</body>", NOTICE + b"</body>", 1) if b"</body>" in content else content + NOTICE
                    headers = [(k, v) for k, v in start_message.get("headers", [])
                               if k.lower() not in (b"content-length", b"etag")]
                    await send_public({**start_message, "headers": headers + [(b"content-length", str(len(content)).encode())]})
                    await send_public({"type": "http.response.body", "body": content})
                return
            await send_public(message)

        if computational:
            if self.gate.locked():
                return await deny("Demo computation is busy; retry shortly.", 503)(scope, receive, send_public)
            async with self.gate:
                return await self.app(scope, receive, annotated_send)
        return await self.app(scope, receive, annotated_send)


def create_app():
    """Factory avoids touching api/main.py or altering the local entry point."""
    mode = os.environ.get("MARTIAN_PUBLIC_MODE", "off")
    if mode not in ("off", "readonly"):
        raise ValueError("MARTIAN_PUBLIC_MODE must be off or readonly")
    from .main import app, DATA
    if mode == "off":
        return app
    from .plan import PlanRequest
    snapshot = json.loads((Path(DATA) / "plans/last_plan.json").read_text(encoding="utf-8"))
    return PublicMode(app, mode=mode, snapshot=snapshot,
                      normalize=lambda value: PlanRequest.model_validate(value).model_dump())
