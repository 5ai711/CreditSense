"""End-to-end measurements of the running platform, reported in the paper's platform section.

Start the stack first (``docker compose up -d --build --wait`` from the repository root), then:

    python platform_bench.py --n 200 --out results/platform.json

Every application is submitted through the web app's proxy exactly as the browser submits it,
by a freshly registered applicant with a unique, valid PAN and GSTIN, so no fraud rule fires.
Two experiments are run:

1. latency of ``POST /api/applications``: compliance gate, feature derivation, the ML call
   with its SHAP ledger, contract validation, persistence and audit records, all in one request;
2. degradation: the ML service is stopped with ``docker compose stop``, applications keep
   arriving, then the service is started again and we time how long scoring takes to resume.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from creditsense_sim.gstin import check_char  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def call(base: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | None]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers=headers, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def random_pan(rng: random.Random) -> str:
    letters = string.ascii_uppercase
    return ("".join(rng.choice(letters) for _ in range(3)) + rng.choice("CPF") + rng.choice(letters)
            + f"{rng.randrange(10000):04d}" + rng.choice(letters))


def application(rng: random.Random) -> dict:
    pan = random_pan(rng)
    body = "36" + pan + "1Z"
    gstin = body + check_char(body)
    revenue = rng.uniform(2, 25)
    revenues = [round(revenue * rng.uniform(0.7, 1.3), 2) for _ in range(6)]
    inflow = round(revenue * rng.uniform(0.8, 1.1), 2)
    udyam = f"UDYAM-TS-{rng.randrange(1, 40):02d}-{rng.randrange(10**7):07d}"
    return {
        "business": {
            "businessName": f"Bench Enterprise {pan[-5:]}", "ownerName": "Bench Owner",
            "sector": rng.choice(["MANUFACTURING", "RETAIL", "SERVICES", "TRADING", "HOSPITALITY", "AGRI_ALLIED"]),
            "pan": pan, "gstin": gstin, "udyamNumber": udyam, "addressLine": "Plot 7, Industrial Area",
            "city": "Hyderabad", "stateCode": "36", "pincode": "500039",
            "businessStartDate": f"{rng.randrange(2005, 2025)}-{rng.randrange(1, 13):02d}-01",
        },
        "loan": {"amount": round(rng.uniform(2, 60), 2), "purpose": "WORKING_CAPITAL",
                 "tenureMonths": rng.choice([12, 24, 36, 48, 60])},
        "financials": {
            "monthlyRevenues": revenues, "existingDebt": round(revenue * 12 * rng.uniform(0, 1.2), 2),
            "avgMonthlyInflow": inflow, "avgMonthlyOutflow": round(inflow * rng.uniform(0.85, 1.1), 2),
            "avgBankBalance": round(inflow * rng.uniform(0.1, 2.5), 2),
            "gstOnTimeFilingPct": round(rng.uniform(55, 100), 1), "tradeReferences": rng.randrange(0, 10),
            "delinquencyEvents": rng.choice([0, 0, 0, 1, 2, 4]), "digitalTxnPerMonth": rng.randrange(0, 300),
        },
        "documents": [
            {"type": "PAN", "documentNumber": pan},
            {"type": "UDYAM", "documentNumber": udyam},
            {"type": "ADDRESS_PROOF", "documentNumber": f"EB-{rng.randrange(10**7):07d}"},
            {"type": "BANK_STATEMENT", "documentNumber": f"STMT-{rng.randrange(10**6):06d}",
             "monthsCovered": rng.choice([6, 9, 12])},
        ],
    }


def applicant(base: str, run: str, i: int) -> str:
    status, body = call(base, "/auth/register", {"email": f"bench-{run}-{i}@creditsense.test",
                                                  "password": "Bench@12345", "fullName": "Bench Owner"})
    if status != 201:
        raise RuntimeError(f"registration failed: {status} {body}")
    return body["accessToken"]


def submit(base: str, token: str, app: dict) -> tuple[float, str]:
    started = time.perf_counter()
    status, body = call(base, "/applications", app, token)
    elapsed = (time.perf_counter() - started) * 1000
    if status != 201:
        raise RuntimeError(f"submission failed: {status} {body}")
    return elapsed, body["status"]


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)


def wait_healthy(service: str, timeout: float = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = subprocess.run(["docker", "compose", "ps", "--format", "{{.Service}} {{.Health}}"], cwd=ROOT,
                             capture_output=True, text=True).stdout
        if f"{service} healthy" in out:
            return
        time.sleep(0.5)
    raise TimeoutError(f"{service} did not become healthy")


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:3000/api")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--outage-calls", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="results/platform.json")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    run = f"{int(time.time())}"

    # 1. latency under normal operation (a few warm-up calls are discarded)
    tokens = [applicant(args.base, run, i) for i in range(args.n + 5)]
    for t in tokens[:5]:
        submit(args.base, t, application(rng))
    latencies, statuses = [], Counter()
    for t in tokens[5:]:
        ms, status = submit(args.base, t, application(rng))
        latencies.append(ms)
        statuses[status] += 1
    print(f"latency: median {statistics.median(latencies):.1f} ms, p95 {pct(latencies, 0.95):.1f} ms, {dict(statuses)}")

    # 2. degradation and recovery
    spare = [applicant(args.base, run, 10_000 + i) for i in range(args.outage_calls + 40)]
    compose("stop", "ml-service")
    outage = []
    try:
        for t in spare[:args.outage_calls]:
            ms, status = submit(args.base, t, application(rng))
            outage.append({"ms": round(ms, 1), "status": status})
            print(f"  ML down: {status} in {ms:.0f} ms")
    finally:
        compose("start", "ml-service")
    wait_healthy("ml-service")
    healthy_at = time.time()
    recovery = None
    for t in spare[args.outage_calls:]:
        ms, status = submit(args.base, t, application(rng))
        if status != "MANUAL_REVIEW":
            recovery = {"seconds_after_healthy": round(time.time() - healthy_at, 1), "status": status}
            break
        time.sleep(2)
    print(f"  recovery: {recovery}")

    result = {
        "n": len(latencies),
        "latency_ms": {"median": round(statistics.median(latencies), 1), "p95": round(pct(latencies, 0.95), 1),
                       "mean": round(statistics.fmean(latencies), 1), "max": round(max(latencies), 1)},
        "statuses": dict(statuses),
        "outage": outage,
        "recovery": recovery,
        "environment": {"cpu": platform.processor() or platform.machine(), "cores": os.cpu_count(),
                        "python": platform.python_version()},
    }
    out = Path(__file__).resolve().parent / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
