package com.creditsense.risk;

/** A score arrived without a complete, additive explanation, so it must not be used. */
public class ExplanationContractViolation extends RuntimeException {
    public ExplanationContractViolation(String message) {
        super(message);
    }
}
