# CampusDesk

Campus complaint and service-request tracker. Students raise complaints, an admin assigns them to staff, staff resolve them, the student confirms. Built as the application layer for a Cloud Computing and DevOps project (AWS, Docker, Kubernetes, Terraform, Ansible, Jenkins, Prometheus, Grafana, CloudWatch).

Team: Aby Joseph (RA2311026011009), Kevin John Manoj (RA2311026011023), Syed Wahid (RA2311026011016).

## Stack

Flask 3, SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF (CSRF), Flask-Limiter, gunicorn, PostgreSQL 16 (SQLite for tests and quick runs), prometheus-client, a hand-written CSS design system, self-hosted fonts and no front-end build step.

## Run locally (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
export FLASK_APP=wsgi.py             # PowerShell: $env:FLASK_APP="wsgi.py"
flask db upgrade                     # creates campusdesk.db (SQLite)
flask seed                           # categories + demo users
flask run --port 8000
```

Open http://localhost:8000. Demo logins (password `ChangeMe123!`, change with `SEED_PASSWORD`):

| Role | Email |
| --- | --- |
| Admin | admin@campusdesk.in |
| Staff | staff1@campusdesk.in, staff2@campusdesk.in |
| Student | student@campusdesk.in |

## Run locally with Docker (app + PostgreSQL)

```bash
docker compose up --build
```

Open http://localhost:8000. Stop with `docker compose down -v`.

## Tests

```bash
pytest --cov=app --cov-fail-under=80
```

## Endpoints

- Pages: `/`, `/login`, `/register`, `/dashboard`, `/complaints`, `/complaints/new`, `/complaints/<id>`, `/admin/categories`
- JSON API: `/api/auth/*`, `/api/complaints[...]`, `/api/categories`, `/api/users?role=staff`, `/api/stats/summary`
- Ops: `/healthz` (liveness), `/readyz` (database reachable), `/metrics` (Prometheus)

## Prometheus metrics

`http_requests_total{method,endpoint,status}`, `http_request_duration_seconds` (histogram), `campusdesk_complaints_created_total{category}`, `campusdesk_complaints_open{status}`, `campusdesk_login_failures_total`.

The container runs one gunicorn worker with four threads on purpose: prometheus-client keeps counters in process memory, so several workers would each report different values.

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql+psycopg2://user:pass@host:5432/campusdesk` | `sqlite:///campusdesk.db` |
| `SECRET_KEY` | Session and CSRF signing key | dev-only value (change it) |
| `SEED_PASSWORD` | Password for demo users created by `flask seed` | `ChangeMe123!` |
| `LOG_LEVEL` | Python log level | `INFO` |

## Repository layout

```
app/            Flask application (models, services, api, pages, templates)
migrations/     Alembic migrations (flask db upgrade)
tests/          pytest suite (31 tests, about 93% coverage)
k8s/            namespace, configmap, deployment + service, secret template
Jenkinsfile     test -> build -> push -> deploy -> smoke test
Dockerfile      multi-stage, non-root
docker-compose.yml   local app + PostgreSQL only
terraform/, ansible/, monitoring/   added in the next build stages
```

## Never commit

Real secrets, `.env`, `*.pem` keys, `terraform.tfstate`, `*.tfvars`. See `.gitignore`.

