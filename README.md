# CreditSense

Explainable, compliance-gated credit risk assessment for MSME (micro, small and medium enterprise) lending.

An application first passes a **deterministic compliance gate** (GSTIN check character, KYC completeness, fraud rules).
Only then does a **trained XGBoost model** score it, and every score comes with a **SHAP explanation ledger**.
The ledger is a list of signed line items that add up exactly to the score. A score without a valid explanation is
never shown to anyone. Loan officers decide, with a mandatory reason when they override the model. Administrators
watch the portfolio and the model's live performance and run the champion/challenger retraining loop. Every
state change is written to an append-only audit trail.

## Quick start

```bash
docker compose up --build
```

| What | Where |
|---|---|
| Web app | http://localhost:3000 |
| API docs (Swagger UI) | http://localhost:8080/swagger-ui.html |

The first build trains the model inside the ML image (about a minute), and the backend seeds demo data on first start.

**Demo accounts** (password `Demo@1234`):

| Role | Email | Start at |
|---|---|---|
| Applicant | `applicant@creditsense.demo` | My loans: an approved loan, one awaiting a decision, one stopped by the KYC rule |
| Loan officer | `officer@creditsense.demo` | Queue: scored applications waiting for a decision, each with its ledger |
| Admin | `admin@creditsense.demo` | Portfolio: KPIs, risk mix, default trend, champion vs challenger; Audit trail |

The seed pushes about 50 applications through the real pipeline over a simulated year. It includes one example of
each compliance failure: blacklisted PAN, PAN reused on another account, address in a different state than the GST
registration, GSTIN with a typing error, too many applications in 30 days, and incomplete KYC. Older approved loans
are matured with simulated outcomes, and one champion/challenger retrain is run.

To see the manual-review path, stop the model (`docker compose stop ml-service`) and submit an application as the
applicant. The circuit breaker opens and the application goes to `MANUAL_REVIEW` with the reason recorded.
`docker compose start ml-service` brings scoring back.

## Architecture

```
┌──────────────────────┐  REST   ┌───────────────────────────┐  REST (features only)  ┌──────────────────────────┐
│ React + Vite + TS     │◄──────►│ Spring Boot core API       │◄──────────────────────►│ FastAPI ML service        │
│ Tailwind, React Query │ (nginx │ auth · compliance gate ·   │ circuit breaker, retry, │ XGBoost + TreeSHAP ·      │
│ applicant / officer / │  /api) │ orchestration · audit      │ time limiter            │ WOE baseline · registry · │
│ admin dashboards      │        └─────────────┬─────────────┘                         │ champion/challenger       │
└──────────────────────┘                      ▼                                        └────────────┬─────────────┘
                                   PostgreSQL (Flyway schema,                             /data volume: training set,
                                   SHAP ledgers as JSONB,                                 holdout, feedback outcomes,
                                   append-only audit log)                                 versioned model registry
```

* **backend/**: the system of record and the only service the browser talks to. It owns authentication (JWT access
  tokens plus rotating refresh tokens, BCrypt), role checks with `@PreAuthorize` and ownership checks, the compliance
  gate, calls to the ML service, decisions, portfolio analytics and the audit trail.
* **ml-service/**: stateless from the caller's view. It receives an engineered feature vector (never names, PAN, GSTIN
  or documents) and returns a probability of default, a risk band, the model version and the full ledger. It also
  simulates loan outcomes and runs retraining. See [ml-service/README.md](ml-service/README.md).
* **frontend/**: role-based dashboards built as a risk-desk instrument. The signature element is the hand-built
  ledger waterfall.
* **research/**: the reproducible experiments behind the accompanying paper (same data generator as the ML service).

### Application lifecycle

```
SUBMITTED ─gate─► COMPLIANCE_FAILED            (terminal; the failing rules are shown, it is not a "low score")
    └─passed─► COMPLIANCE_REVIEW ─scored + explained─► RISK_SCORED ─officer─► APPROVED / REJECTED
                    └─ML down or explanation invalid─► MANUAL_REVIEW ─underwriter─► APPROVED / REJECTED
```

## Design decisions that matter

* **Compliance is never learned.** GST validity (structure, state code, Luhn mod-36 check character, PAN match),
  KYC completeness (required PAN, Udyam, address proof and at least 6 months of bank statements, weighted score
  of 0.8 or more) and fraud rules (duplicate PAN, address state mismatch, blacklist, velocity) are pure functions with
  their own unit tests. A failure is terminal and explained.
* **No unexplained scores.** The ML service withholds a prediction (HTTP 503) if the SHAP decomposition does not add
  up. The backend re-validates the contract: every feature present once, contributions finite, base value plus
  contributions equal to the logit of the PD, and the band consistent with the PD. A violation routes the application
  to manual review instead of storing the score.
* **Calibrated scores that stay explainable.** Class weighting inflates raw XGBoost probabilities, so the margin is
  recalibrated with Platt scaling. Because that map is affine, the SHAP ledger stays exact on the calibrated scale.
* **Graceful degradation.** The ML client runs behind Resilience4j `TimeLimiter`, `CircuitBreaker` and `Retry`. If the
  model is unreachable, the application moves to `MANUAL_REVIEW` with the reason recorded.
* **Auditability.** Every state change writes an audit row with actor, action and before/after state. A database
  trigger rejects `UPDATE` and `DELETE` on `audit_logs`. Automatic pipeline steps are attributed to `system`, and
  officer re-runs to the officer.
* **Model lifecycle.** Matured loans get simulated 12-month outcomes from the same ground-truth process as the
  training data. `/retrain` trains a challenger on base data plus feedback and promotes it only if its AUC on a
  holdout that no model trains on beats the champion's. Every comparison is logged and charted.

## Running and testing each part

```bash
# ML service (Python 3.11)
cd ml-service && pip install -r requirements-dev.txt && pytest
ML_DATA_DIR=data uvicorn creditsense_ml.api:app --port 8000

# Backend (Java 21). Integration tests use Testcontainers and need Docker;
# run only the unit tests with -Punit
cd backend && mvn test
ML_SERVICE_TOKEN= SEED_DEMO_DATA=true mvn spring-boot:run   # expects Postgres on localhost:5432

# Frontend (Node 22)
cd frontend && npm ci && npm test && npm run dev            # proxies /api to localhost:8080
```

| Suite | What it covers |
|---|---|
| `ml-service/tests` | generator properties, additivity of every explanation, withheld scores, persisted metrics, feedback de-duplication, champion/challenger promotion, API validation and service token |
| `backend` unit tests | GSTIN (every single-character substitution caught), each compliance rule and its edge cases, the gate service, explanation contract, feature derivation, risk orchestration and fallback, ML client retry, timeout and circuit breaker, decision rules, JWT |
| `backend` integration test | real PostgreSQL: applicant to decision with the audit sequence, ownership (404 for another applicant's application), compliance failure blocking scoring, ML outage leading to manual review, field-level validation errors, append-only audit trigger, refresh-token rotation and reuse detection |
| `frontend` | GSTIN rules identical to the backend's, and the ledger balancing and labelling |

## API

| Method | Path | Role |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout` | public |
| POST | `/api/applications` (submit; runs the gate, then scoring) | applicant |
| GET | `/api/applications/mine` | applicant |
| GET | `/api/applications/{id}` | owner or staff |
| GET | `/api/applications?status=&band=&q=` | officer, admin |
| POST | `/api/applications/{id}/compliance-check`, `/risk-assessment` | officer, admin |
| POST | `/api/applications/{id}/decision` | officer |
| GET | `/api/portfolio/analytics` | admin |
| GET | `/api/audit-logs` | admin |
| POST | `/api/admin/simulate-maturity`, `/api/admin/retrain`; GET `/api/admin/model` | admin |

## Configuration

Copy `.env.example` to `.env`. **Change `JWT_SECRET` and `ML_SERVICE_TOKEN` before running anywhere but your own
machine.** Set `SEED_DEMO_DATA=false` for an empty system.

## Honest limitations

* The training data are simulated from a documented generator (see `ml-service/creditsense_ml/generator.py`). The
  model's metrics describe that population, not a real loan book.
* GST and KYC checks validate structure, check characters and internal consistency. They do not call the live GSTN,
  NSDL or Udyam registries. The blacklist holds demo entries.
* The web client keeps tokens in `localStorage` for simplicity. A production deployment should move the refresh
  token to an `HttpOnly` cookie.
