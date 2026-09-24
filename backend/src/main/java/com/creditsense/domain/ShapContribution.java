package com.creditsense.domain;

/** One line of the explanation ledger, on the calibrated log-odds scale. */
public record ShapContribution(String feature, Object featureValue, double shapContribution) {}
