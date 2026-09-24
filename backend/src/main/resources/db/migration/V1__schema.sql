-- CreditSense core schema. Monetary amounts are in INR lakh.

CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
    full_name     VARCHAR(120) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('APPLICANT', 'LOAN_OFFICER', 'ADMIN')),
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash VARCHAR(64)    NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);

-- Business profile of an applicant user (one per user).
CREATE TABLE applicants (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT       NOT NULL UNIQUE REFERENCES users (id),
    business_name       VARCHAR(200) NOT NULL,
    owner_name          VARCHAR(120) NOT NULL,
    sector              VARCHAR(20)  NOT NULL,
    pan                 VARCHAR(10)     NOT NULL,
    gstin               VARCHAR(15)     NOT NULL,
    udyam_number        VARCHAR(19),
    address_line        VARCHAR(300) NOT NULL,
    city                VARCHAR(100) NOT NULL,
    state_code          VARCHAR(2)      NOT NULL,
    pincode             VARCHAR(6)      NOT NULL,
    business_start_date DATE         NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
-- Not unique on purpose: the same PAN on two accounts is a fraud signal the gate must see.
CREATE INDEX idx_applicants_pan ON applicants (pan);
CREATE INDEX idx_applicants_gstin ON applicants (gstin);

CREATE TABLE loan_applications (
    id                     BIGSERIAL PRIMARY KEY,
    reference              VARCHAR(20)   NOT NULL UNIQUE,
    applicant_id           BIGINT        NOT NULL REFERENCES applicants (id),
    amount_requested       NUMERIC(14, 2) NOT NULL CHECK (amount_requested > 0),
    purpose                VARCHAR(30)   NOT NULL,
    tenure_months          INT           NOT NULL CHECK (tenure_months BETWEEN 3 AND 120),
    status                 VARCHAR(30)   NOT NULL,
    -- financial snapshot declared with this application
    monthly_revenues       JSONB         NOT NULL,
    existing_debt          NUMERIC(14, 2) NOT NULL,
    avg_monthly_inflow     NUMERIC(14, 2) NOT NULL,
    avg_monthly_outflow    NUMERIC(14, 2) NOT NULL,
    avg_bank_balance       NUMERIC(14, 2) NOT NULL,
    gst_on_time_filing_pct NUMERIC(5, 2) NOT NULL,
    trade_references       INT           NOT NULL,
    delinquency_events     INT           NOT NULL,
    digital_txn_per_month  INT           NOT NULL,
    -- pipeline results
    kyc_score              NUMERIC(5, 4),
    latest_pd              NUMERIC(8, 6),
    latest_risk_band       VARCHAR(10),
    model_recommendation   VARCHAR(10),
    manual_review_reason   VARCHAR(500),
    -- human decision
    decision               VARCHAR(10),
    decision_reason        VARCHAR(1000),
    decision_override      BOOLEAN,
    decided_by             BIGINT REFERENCES users (id),
    decided_at             TIMESTAMPTZ,
    -- simulated repayment outcome once the loan has matured
    outcome                VARCHAR(10),
    outcome_recorded_at    TIMESTAMPTZ,
    submitted_at           TIMESTAMPTZ   NOT NULL,
    updated_at             TIMESTAMPTZ   NOT NULL,
    version                BIGINT        NOT NULL DEFAULT 0
);
CREATE INDEX idx_applications_status ON loan_applications (status);
CREATE INDEX idx_applications_applicant ON loan_applications (applicant_id, submitted_at);

CREATE TABLE kyc_documents (
    id                BIGSERIAL PRIMARY KEY,
    application_id    BIGINT      NOT NULL REFERENCES loan_applications (id) ON DELETE CASCADE,
    doc_type          VARCHAR(20) NOT NULL,
    document_number   VARCHAR(50) NOT NULL,
    months_covered    INT,
    verified          BOOLEAN     NOT NULL DEFAULT FALSE,
    verification_note VARCHAR(300)
);
CREATE INDEX idx_kyc_documents_application ON kyc_documents (application_id);

CREATE TABLE compliance_checks (
    id             BIGSERIAL PRIMARY KEY,
    application_id BIGINT       NOT NULL REFERENCES loan_applications (id) ON DELETE CASCADE,
    check_type     VARCHAR(30)  NOT NULL,
    category       VARCHAR(10)  NOT NULL,
    passed         BOOLEAN      NOT NULL,
    reason         VARCHAR(500) NOT NULL,
    details        JSONB,
    evaluated_at   TIMESTAMPTZ  NOT NULL
);
CREATE INDEX idx_compliance_checks_application ON compliance_checks (application_id);

CREATE TABLE risk_assessments (
    id                     BIGSERIAL PRIMARY KEY,
    application_id         BIGINT           NOT NULL REFERENCES loan_applications (id) ON DELETE CASCADE,
    probability_of_default NUMERIC(8, 6)    NOT NULL,
    risk_band              VARCHAR(10)      NOT NULL,
    model_version          VARCHAR(40)      NOT NULL,
    base_value             DOUBLE PRECISION NOT NULL,
    shap_contributions     JSONB            NOT NULL,
    feature_vector         JSONB            NOT NULL,
    assessed_at            TIMESTAMPTZ      NOT NULL
);
CREATE INDEX idx_risk_assessments_application ON risk_assessments (application_id, assessed_at DESC);

-- Append-only record of every state-changing action.
CREATE TABLE audit_logs (
    id           BIGSERIAL PRIMARY KEY,
    actor_id     BIGINT,
    actor_email  VARCHAR(255) NOT NULL,
    actor_role   VARCHAR(20)  NOT NULL,
    action       VARCHAR(50)  NOT NULL,
    entity_type  VARCHAR(40)  NOT NULL,
    entity_id    VARCHAR(40),
    before_state JSONB,
    after_state  JSONB,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_created ON audit_logs (created_at DESC);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_action ON audit_logs (action);

CREATE TABLE blacklist_entries (
    id              BIGSERIAL PRIMARY KEY,
    identifier_type VARCHAR(10)  NOT NULL CHECK (identifier_type IN ('PAN', 'GSTIN')),
    identifier      VARCHAR(15)  NOT NULL,
    reason          VARCHAR(300) NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (identifier_type, identifier)
);

-- The audit trail must be defensible: reject edits and deletes at the database level.
CREATE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_no_update
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();
