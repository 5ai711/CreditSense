package com.creditsense.domain;

import java.util.Set;

/**
 * Lifecycle of a loan application.
 *
 * <pre>
 * SUBMITTED ──gate──▶ COMPLIANCE_FAILED (terminal, with reasons)
 *     │
 *     └──gate passed──▶ COMPLIANCE_REVIEW ──scored + explained──▶ RISK_SCORED ──officer──▶ APPROVED / REJECTED
 *                              │
 *                              └──ML down or explanation invalid──▶ MANUAL_REVIEW ──underwriter──▶ APPROVED / REJECTED
 * </pre>
 */
public enum ApplicationStatus {
    SUBMITTED,
    COMPLIANCE_REVIEW,
    COMPLIANCE_FAILED,
    RISK_SCORED,
    APPROVED,
    REJECTED,
    MANUAL_REVIEW;

    public static final Set<ApplicationStatus> SCORABLE = Set.of(COMPLIANCE_REVIEW, RISK_SCORED, MANUAL_REVIEW);
    public static final Set<ApplicationStatus> DECIDABLE = Set.of(RISK_SCORED, MANUAL_REVIEW);

    public boolean isTerminal() {
        return this == COMPLIANCE_FAILED || this == APPROVED || this == REJECTED;
    }
}
