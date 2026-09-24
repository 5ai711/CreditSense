package com.creditsense.risk;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import com.creditsense.domain.Applicant;
import com.creditsense.domain.LoanApplication;
import com.creditsense.domain.Sector;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class FeatureVectorBuilderTest {

    static LoanApplication sample() {
        Applicant a = new Applicant();
        a.setSector(Sector.AGRI_ALLIED);
        a.setBusinessStartDate(LocalDate.of(2020, 9, 24));
        LoanApplication app = new LoanApplication();
        app.setApplicant(a);
        app.setSubmittedAt(Instant.parse("2026-09-24T10:00:00Z"));
        app.setMonthlyRevenues(List.of(bd(8), bd(12), bd(10), bd(10), bd(8), bd(12)));
        app.setExistingDebt(bd(60));
        app.setAvgMonthlyInflow(bd(11));
        app.setAvgMonthlyOutflow(bd(10));
        app.setAvgBankBalance(bd(5));
        app.setGstOnTimeFilingPct(bd(92));
        app.setTradeReferences(4);
        app.setDelinquencyEvents(1);
        app.setAmountRequested(bd(30));
        app.setKycScore(new BigDecimal("0.9500"));
        app.setDigitalTxnPerMonth(150);
        return app;
    }

    static BigDecimal bd(double v) {
        return BigDecimal.valueOf(v);
    }

    @Test
    void derivesEveryModelFeatureFromTheApplication() {
        Map<String, Object> f = new FeatureVectorBuilder().build(sample());

        assertThat(f.keySet()).containsExactlyInAnyOrderElementsOf(FeatureVectorBuilder.FEATURES);
        assertThat((double) f.get("business_vintage")).isCloseTo(6.0, within(0.01));
        assertThat((double) f.get("monthly_revenue")).isEqualTo(10.0);
        assertThat((double) f.get("revenue_volatility")).isCloseTo(Math.sqrt(8.0 / 3) / 10, within(1e-6));
        assertThat((double) f.get("gst_filing_consistency")).isEqualTo(0.92);
        assertThat((double) f.get("debt_to_revenue")).isEqualTo(0.5);
        assertThat((double) f.get("inflow_outflow_ratio")).isEqualTo(1.1);
        assertThat((double) f.get("balance_cover")).isEqualTo(0.5);
        assertThat((double) f.get("loan_to_revenue")).isEqualTo(0.25);
        assertThat(f.get("sector")).isEqualTo("Agri-allied");
    }

    @Test
    void neverSendsPersonalData() {
        assertThat(new FeatureVectorBuilder().build(sample()).keySet())
                .doesNotContain("pan", "gstin", "businessName", "ownerName");
    }
}
