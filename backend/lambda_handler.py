"""
AWS Lambda entrypoint for Argus AI, using Mangum to adapt the FastAPI ASGI
app to API Gateway / Lambda events. Deploy behind API Gateway (HTTP API)
to run the whole backend as a managed, autoscaling cloud function --
no server to patch or provision.

Local dev still runs the same `app` via `uvicorn app.main:app`; this file
only adds the cloud entrypoint on top.
"""

from mangum import Mangum

from app.main import app

handler = Mangum(app)
