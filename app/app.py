"""NERDS uc - Wild Cam Observation Log.

Logs which animal was visible in which live stream and when.
Configuration via environment variables:
  DATABASE_URL  e.g. postgresql://user:pass@db-host:5432/wildcam
                (falls back to a local SQLite file if unset)
  SECRET_KEY    Flask session secret
"""
import os
import socket
import time
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
db_url = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(app.instance_path, "wildcam.db"))
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)  # use psycopg 3 driver
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
os.makedirs(app.instance_path, exist_ok=True)

db = SQLAlchemy(app)

# Shown in the page footer so you can see which worker/container served the request
NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname())


class Sighting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream = db.Column(db.String(120), nullable=False)
    animal = db.Column(db.String(120), nullable=False)
    seen_from = db.Column(db.DateTime, nullable=False)
    seen_until = db.Column(db.DateTime)
    count = db.Column(db.Integer, default=1)
    observer = db.Column(db.String(80))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    # Retry: the DB server may not be reachable yet, and several workers/nodes
    # may race to create the table on first start.
    for attempt in range(10):
        try:
            db.create_all()
            break
        except Exception as exc:
            app.logger.warning("DB init attempt %d failed: %s", attempt + 1, exc)
            time.sleep(3)


def parse_dt(value):
    return datetime.fromisoformat(value) if value else None


@app.route("/", methods=["GET"])
def index():
    stream_filter = request.args.get("stream", "")
    query = Sighting.query
    if stream_filter:
        query = query.filter_by(stream=stream_filter)
    sightings = query.order_by(Sighting.seen_from.desc()).all()
    streams = [s for (s,) in db.session.query(Sighting.stream).distinct().order_by(Sighting.stream)]
    animals = [a for (a,) in db.session.query(Sighting.animal).distinct().order_by(Sighting.animal)]
    return render_template(
        "index.html",
        sightings=sightings,
        streams=streams,
        animals=animals,
        stream_filter=stream_filter,
        node=NODE_NAME,
        now=datetime.now().strftime("%Y-%m-%dT%H:%M"),
    )


@app.route("/add", methods=["POST"])
def add():
    f = request.form
    stream, animal = f.get("stream", "").strip(), f.get("animal", "").strip()
    try:
        seen_from = parse_dt(f.get("seen_from"))
        seen_until = parse_dt(f.get("seen_until"))
    except ValueError:
        seen_from = None
    if not stream or not animal or not seen_from:
        flash("Stream, animal and 'seen from' are required.", "error")
        return redirect(url_for("index"))
    if seen_until and seen_until < seen_from:
        flash("'Seen until' must be after 'seen from'.", "error")
        return redirect(url_for("index"))
    db.session.add(Sighting(
        stream=stream,
        animal=animal,
        seen_from=seen_from,
        seen_until=seen_until,
        count=max(1, int(f.get("count") or 1)),
        observer=f.get("observer", "").strip() or None,
        notes=f.get("notes", "").strip() or None,
    ))
    db.session.commit()
    flash(f"Logged {animal} on {stream}.", "ok")
    return redirect(url_for("index"))


@app.route("/delete/<int:sighting_id>", methods=["POST"])
def delete(sighting_id):
    db.session.delete(db.get_or_404(Sighting, sighting_id))
    db.session.commit()
    flash("Entry deleted.", "ok")
    return redirect(url_for("index"))


@app.route("/health")
def health():
    db.session.execute(db.text("SELECT 1"))
    return {"status": "ok", "node": NODE_NAME}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
