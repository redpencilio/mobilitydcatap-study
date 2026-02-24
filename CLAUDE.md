# MobilityDCAT-AP Validator

A [semantic.works](https://semantic.works) / mu-project web application that validates DCAT feeds against the [mobilityDCAT-AP specification](https://mobilitydcat-ap.github.io/mobilityDCAT-AP/).

## What it does

Users paste a DCAT endpoint URL. The backend fetches the feed (supporting CKAN DCAT APIs, Hydra collections, and LDES streams), loads it into Virtuoso, runs property compliance and controlled vocabulary analysis, and produces a persistent interactive HTML report accessible at a shareable URL.

## Stack

| Service | Image / Build | Role |
|---|---|---|
| `identifier` | `semtech/mu-identifier` | Session management, sits in front of dispatcher |
| `dispatcher` | `semtech/mu-dispatcher` | Routes requests to the right service |
| `frontend` | built from `./frontend` | EmberJS app served as static files |
| `resource` | `semtech/mu-cl-resources` | CRUD API for `ValidationJob` linked data |
| `triplestore` | `redpencil/virtuoso` | RDF triple store (stores jobs + fetched data) |
| `delta-notifier` | `semtech/mu-delta-notifier` | Watches for new pending jobs in Virtuoso |
| `job-runner` | built from `./services/job-runner` | Receives delta callbacks, triggers Python service |
| `validation` | built from `./services/validation` | Fetches DCAT data, runs analysis, generates reports |
| `reports` | `nginx:alpine` | Serves generated HTML reports as static files |

## Running locally

```bash
# Standard
docker compose up -d

# Development (exposes Virtuoso :8890, validation :5000, identifier :80)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Visit `http://localhost`. The app is served through `identifier` → `dispatcher` → `frontend`.

## Job lifecycle

1. User submits a DCAT endpoint URL in the Ember frontend
2. Frontend creates a `ValidationJob` via `POST /api/jobs` (mu-cl-resources), with `status=pending` and a unique `ext:graphUri`
3. `delta-notifier` detects the new `status=pending` triple and POSTs to `job-runner`
4. `job-runner` POSTs `{job_uri}` to `POST /run-job` on the `validation` service
5. `validation` service (background thread):
   - Fetches RDF from the endpoint (auto-detects CKAN / Hydra / LDES)
   - Loads triples into the job's named graph in Virtuoso
   - Runs property compliance analysis and vocabulary analysis
   - Generates a self-contained HTML report in `data/reports/`
   - Drops the named graph to free storage
   - Updates the job: `status=completed`, `reportUrl=<url>`
6. Frontend polls `GET /api/jobs/:id` every 3 seconds and shows the report link when done

## Key directories

```
config/
  dispatcher/dispatcher.ex     # URL routing rules
  resources/domain.lisp        # ValidationJob linked data schema
  resources/repository.lisp    # Namespace prefixes
  delta/rules.js               # Delta-notifier trigger rule
  reports-nginx/nginx.conf     # Static report server config

frontend/                      # EmberJS app
  Dockerfile                   # Multi-stage: node:22 build → semtech/static-file-service
  app/models/job.js            # Job ember-data model
  app/routes/jobs/new.js       # Form route
  app/routes/jobs/show.js      # Status/result route (starts polling)
  app/controllers/jobs/new.js  # Form submit → creates job → redirects
  app/controllers/jobs/show.js # 3-second polling task
  app/styles/app.css           # redpencil.io branding, plain CSS (no UI framework)

services/validation/           # Python Flask service
  app.py                       # POST /run-job, GET /health
  dcat_fetcher.py              # Fetch CKAN / Hydra / LDES (full pagination)
  property_analysis.py         # MobilityDCAT-AP property compliance (class-based)
  vocabulary_checker.py        # Controlled vocabulary analysis (class-based)
  report_generator.py          # Self-contained HTML dashboard with Chart.js
  sparql_helpers.py            # Shared SPARQL query/update/graph-load helpers

services/job-runner/           # Node.js delta-notifier bridge (~50 lines)
  app.js                       # POST /delta → trigger validation service

data/
  db/                          # Virtuoso data (gitignored)
  reports/                     # Generated HTML reports (gitignored)
```

## Frontend development

The frontend is built into the Docker image (multi-stage build). To iterate quickly without rebuilding the image each time, run Ember locally:

```bash
cd frontend
npm install
npm run start          # ember serve, proxies /api to http://localhost/api
```

Rebuild the image after changes:

```bash
docker compose build frontend && docker compose up -d frontend
```

## Validation service development

```bash
# With docker-compose.dev.yml the service is exposed on :5000
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or run locally (requires a running Virtuoso)
cd services/validation
pip install -r requirements.txt
SPARQL_ENDPOINT=http://localhost:8890/sparql REPORTS_DIR=/tmp/reports python app.py
```

The service exposes:
- `POST /run-job` — `{"job_uri": "http://..."}` — starts processing in a background thread, returns 202
- `GET /health` — liveness check

## Adding a new analysis check

1. Add the SPARQL logic to `services/validation/property_analysis.py` or `vocabulary_checker.py`
2. Update `report_generator.py` to include the new data in the HTML output
3. Rebuild: `docker compose build validation && docker compose up -d validation`

## Data model (linked data)

Resource type: `ext:ValidationJob`
API path: `/api/jobs`

| Property | Predicate | Description |
|---|---|---|
| `sourceUrl` | `ext:sourceUrl` | The DCAT endpoint URL submitted by the user |
| `status` | `ext:status` | `pending` → `running` → `completed` / `failed` |
| `endpointType` | `ext:endpointType` | `ldes`, `hydra`, `ckan`, or `dcat` |
| `graphUri` | `ext:graphUri` | Named graph used during analysis (dropped after) |
| `reportUrl` | `ext:reportUrl` | URL to the generated HTML report |
| `errorMessage` | `ext:errorMessage` | Set on failure |
| `createdAt` | `dct:created` | Job creation time |
| `startedAt` | `ext:startedAt` | When processing began |
| `finishedAt` | `ext:finishedAt` | When processing completed or failed |

## Conventions

- **No ember-appuniversum** — styling is plain CSS in `frontend/app/styles/app.css`
- **redpencil.io brand color** — `#E32119`
- **LDES**: full pagination crawl via `tree:node` links with 0.5s polite delay
- **Named graphs**: `http://mu.semte.ch/graphs/validation/<uuid>` — created per job, dropped after report generation
- **Reports**: self-contained HTML files (Chart.js from CDN), no server needed to view them
