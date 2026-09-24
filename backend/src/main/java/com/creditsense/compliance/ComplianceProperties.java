package com.creditsense.compliance;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Thresholds for the compliance gate.
 *
 * @param kycThreshold minimum weighted KYC completeness score
 * @param velocityMaxApplications how many earlier applications are tolerated inside the window
 * @param velocityWindowDays length of the velocity window
 * @param minBankStatementMonths minimum months a bank statement must cover
 */
@ConfigurationProperties("creditsense.compliance")
public record ComplianceProperties(
        double kycThreshold, int velocityMaxApplications, int velocityWindowDays, int minBankStatementMonths) {

    public ComplianceProperties {
        if (kycThreshold <= 0) kycThreshold = 0.8;
        if (velocityMaxApplications <= 0) velocityMaxApplications = 3;
        if (velocityWindowDays <= 0) velocityWindowDays = 30;
        if (minBankStatementMonths <= 0) minBankStatementMonths = 6;
    }
}
