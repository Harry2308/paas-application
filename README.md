# NERDS uc – Wild Cam Observation Log

Flask web app for logging which animal was visible in which live stream, and when.

## Quick start (Docker Compose)
```bash
docker compose up -d --build
```
- Frontend: http://localhost:8000
- Health check: http://localhost:8000/health
- Stop: `docker compose down`

This starts the app on port **8000** and PostgreSQL 16 (internal only, port 5432).

## Run without Docker
```bash
cd app
pip install -r requirements.txt
python app.py
```
Open http://localhost:8000. Without `DATABASE_URL` set, the app uses a local SQLite file.

## Run on a worker VM
```bash
cd app
docker build -t wildcam .
docker run -d --name wildcam --restart unless-stopped -p 8000:8000 \
  -e DATABASE_URL=postgresql://<user>:<password>@<db-server-ip>:5432/<db> \
  -e SECRET_KEY=<same-on-all-workers> \
  -e NODE_NAME=$(hostname) \
  wildcam
```
Point Traefik at `http://<worker-ip>:8000` and use `/health` as the health check.

## Environment variables
| Variable       | Default            | Purpose |
|----------------|--------------------|---------|
| `DATABASE_URL` | local SQLite file  | PostgreSQL connection string |
| `SECRET_KEY`   | `dev-secret-change-me` | Flask session secret |
| `NODE_NAME`    | container hostname | Node name shown in the footer |
