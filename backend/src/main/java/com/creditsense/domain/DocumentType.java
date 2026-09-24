package com.creditsense.domain;

/** KYC documents, their weight in the completeness score and whether the gate requires them. */
public enum DocumentType {
    PAN(0.25, true),
    UDYAM(0.25, true),
    ADDRESS_PROOF(0.20, true),
    BANK_STATEMENT(0.20, true),
    GST_CERTIFICATE(0.10, false);

    private final double weight;
    private final boolean mandatory;

    DocumentType(double weight, boolean mandatory) {
        this.weight = weight;
        this.mandatory = mandatory;
    }

    public double weight() {
        return weight;
    }

    public boolean mandatory() {
        return mandatory;
    }
}
