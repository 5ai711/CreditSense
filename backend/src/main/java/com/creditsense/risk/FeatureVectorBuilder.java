package com.creditsense.risk;

import com.creditsense.domain.Applicant;
import com.creditsense.domain.LoanApplication;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Turns an application into the engineered feature vector the model scores. Only derived
 * numbers leave the backend; names, PAN, GSTIN and documents never reach the ML service.
 */
@Component
public class FeatureVectorBuilder {

    public static final Set<String> FEATURES = Set.of(
            "business_vintage", "monthly_revenue", "revenue_volatility", "gst_filing_consistency",
            "debt_to_revenue", "inflow_outflow_ratio", "balance_cover", "trade_references",
            "delinquency_events", "loan_to_revenue", "kyc_completeness", "digital_txn_volume", "sector");

    public Map<String, Object> build(LoanApplication app) {
        Applicant a = app.getApplicant();
        List<Double> revenues = app.getMonthlyRevenues().stream().map(BigDecimal::doubleValue).toList();
        double mean = revenues.stream().mapToDouble(Double::doubleValue).average().orElse(0);
        double variance = revenues.stream().mapToDouble(r -> (r - mean) * (r - mean)).average().orElse(0);
        double annualRevenue = 12 * mean;
        double outflow = app.getAvgMonthlyOutflow().doubleValue();
        LocalDate asOf = app.getSubmittedAt().atZone(ZoneOffset.UTC).toLocalDate();

        Map<String, Object> f = new LinkedHashMap<>();
        f.put("business_vintage", clamp(ChronoUnit.DAYS.between(a.getBusinessStartDate(), asOf) / 365.25, 0, 100));
        f.put("monthly_revenue", clamp(mean, 0.01, 100_000));
        f.put("revenue_volatility", clamp(mean > 0 ? Math.sqrt(variance) / mean : 0, 0, 5));
        f.put("gst_filing_consistency", clamp(app.getGstOnTimeFilingPct().doubleValue() / 100.0, 0, 1));
        f.put("debt_to_revenue", clamp(app.getExistingDebt().doubleValue() / annualRevenue, 0, 50));
        f.put("inflow_outflow_ratio", clamp(app.getAvgMonthlyInflow().doubleValue() / outflow, 0, 10));
        f.put("balance_cover", clamp(app.getAvgBankBalance().doubleValue() / outflow, 0, 60));
        f.put("trade_references", (double) Math.min(app.getTradeReferences(), 500));
        f.put("delinquency_events", (double) Math.min(app.getDelinquencyEvents(), 100));
        f.put("loan_to_revenue", clamp(app.getAmountRequested().doubleValue() / annualRevenue, 0, 50));
        f.put("kyc_completeness", clamp(app.getKycScore() == null ? 0 : app.getKycScore().doubleValue(), 0, 1));
        f.put("digital_txn_volume", (double) Math.min(app.getDigitalTxnPerMonth(), 1_000_000));
        f.put("sector", a.getSector().modelLabel());
        return f;
    }

    private static double clamp(double v, double lo, double hi) {
        double x = Double.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : lo;
        return Math.round(x * 1e6) / 1e6;
    }
}
