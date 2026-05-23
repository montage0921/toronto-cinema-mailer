"""
FastAPI backend — handles:
  POST /subscribe      — create subscription + send confirmation email
  GET  /confirm        — double opt-in confirmation
  GET  /unsubscribe    — one-click unsubscribe via token
  GET  /health         — uptime check
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from mailer.sender import send_confirmation

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BASE_URL = os.environ.get("BASE_URL", "https://your-domain.com")

VALID_CINEMAS = {
    "paradise",
    "revue",
    "carlton",
    "fox",
    "tiff",
    "yonge-dundas",
    "scotiabank",
    "innis",
    "hot-docs",
    "yonge-eglinton",
    "empress-walk",
}
VALID_FREQUENCIES = {"daily", "weekly"}

app = FastAPI(title="Toronto Cinema Mailer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend domain in prod
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── Request models ────────────────────────────────────────────────────────────


class SubscribeRequest(BaseModel):
    email: EmailStr
    cinemas: list[str]
    frequency: str  # 'daily' or 'weekly'


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/subscribe")
def subscribe(req: SubscribeRequest):
    # Validate
    invalid_cinemas = set(req.cinemas) - VALID_CINEMAS
    if invalid_cinemas:
        raise HTTPException(400, f"Invalid cinema slugs: {invalid_cinemas}")
    if req.frequency not in VALID_FREQUENCIES:
        raise HTTPException(400, f"frequency must be one of {VALID_FREQUENCIES}")
    if not req.cinemas:
        raise HTTPException(400, "Select at least one cinema")

    db = get_db()

    # Check if already subscribed
    existing = (
        db.table("subscribers").select("id,confirmed").eq("email", req.email).execute()
    )
    if existing.data:
        row = existing.data[0]
        if row["confirmed"]:
            return {"message": "Already subscribed — check your email for the digest!"}
        else:
            # Resend confirmation
            token = (
                db.table("subscribers")
                .select("token")
                .eq("email", req.email)
                .execute()
                .data[0]["token"]
            )
            send_confirmation(req.email, token, BASE_URL)
            return {"message": "Confirmation email resent — check your inbox."}

    # Insert new subscriber
    result = (
        db.table("subscribers")
        .insert(
            {
                "email": req.email,
                "cinemas": req.cinemas,
                "frequency": req.frequency,
                "confirmed": False,
            }
        )
        .execute()
    )

    token = result.data[0]["token"]
    send_confirmation(req.email, token, BASE_URL)

    return {"message": "Almost there! Check your email to confirm your subscription."}


@app.get("/confirm")
def confirm(token: str = Query(...)):
    db = get_db()
    result = (
        db.table("subscribers").update({"confirmed": True}).eq("token", token).execute()
    )
    if not result.data:
        raise HTTPException(404, "Invalid or expired confirmation link.")
    return {"message": "Subscription confirmed! You'll receive your first digest soon."}


@app.get("/unsubscribe")
def unsubscribe(token: str = Query(...)):
    db = get_db()
    result = db.table("subscribers").delete().eq("token", token).execute()
    if not result.data:
        raise HTTPException(404, "Invalid unsubscribe link.")
    return {"message": "You've been unsubscribed. Sorry to see you go!"}
