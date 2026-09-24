package com.creditsense.portfolio;

import com.creditsense.domain.ApplicationStatus;
import com.creditsense.domain.LoanApplication;
import com.creditsense.domain.Outcome;
import com.creditsense.domain.RiskBand;
import com.creditsense.repo.LoanApplicationRepository;
import com.creditsense.risk.MlClient;
import com.creditsense.risk.MlUnavailableException;
import java.math.BigDecimal;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Portfolio-level risk view for administrators. */
@Service
public class PortfolioService {

    private final LoanApplicationRepository applications;
    private final MlClient ml;

    public PortfolioService(LoanApplicationRepository applications, MlClient ml) {
        this.applications = applications;
        this.ml = ml;
    }

    public record Kpis(long totalApplications, long pendingReview, long approved, long rejected,
            long complianceFailed, long manualReview, Double approvalRate, Double averageApprovedPd,
            Double observedDefaultRate, long maturedLoans, Double overrideRate) {}

    public record Bucket(double from, double to, long count) {}

    public record TrendPoint(String month, long approved, long matured, long defaulted, Double defaultRate,
            Double averagePd) {}

    @Transactional(readOnly = true)
    public Map<String, Object> analytics() {
        List<LoanApplication> all = applications.findAll();
        Map<ApplicationStatus, Long> byStatus = new EnumMap<>(ApplicationStatus.class);
        for (ApplicationStatus s : ApplicationStatus.values()) byStatus.put(s, 0L);
        all.forEach(a -> byStatus.merge(a.getStatus(), 1L, Long::sum));

        Map<RiskBand, Long> byBand = new EnumMap<>(RiskBand.class);
        for (RiskBand b : RiskBand.values()) byBand.put(b, 0L);
        all.stream().filter(a -> a.getLatestRiskBand() != null).forEach(a -> byBand.merge(a.getLatestRiskBand(), 1L, Long::sum));

        // PD histogram in 2.5-point buckets up to 50%, then one overflow bucket
        long[] counts = new long[21];
        all.stream().map(LoanApplication::getLatestPd).filter(Objects::nonNull).mapToDouble(BigDecimal::doubleValue)
                .forEach(pd -> counts[Math.min(20, (int) Math.floor(pd / 0.025))]++);
        List<Bucket> histogram = new ArrayList<>();
        for (int i = 0; i < 21; i++) histogram.add(new Bucket(i * 0.025, i == 20 ? 1.0 : (i + 1) * 0.025, counts[i]));

        List<LoanApplication> approved = all.stream().filter(a -> a.getStatus() == ApplicationStatus.APPROVED).toList();
        List<LoanApplication> decided = all.stream().filter(a -> a.getDecision() != null).toList();
        List<LoanApplication> matured = approved.stream().filter(a -> a.getOutcome() != null).toList();
        long defaults = matured.stream().filter(a -> a.getOutcome() == Outcome.DEFAULTED).count();
        long rejected = byStatus.get(ApplicationStatus.REJECTED);

        Kpis kpis = new Kpis(all.size(),
                byStatus.get(ApplicationStatus.RISK_SCORED) + byStatus.get(ApplicationStatus.MANUAL_REVIEW),
                approved.size(), rejected, byStatus.get(ApplicationStatus.COMPLIANCE_FAILED),
                byStatus.get(ApplicationStatus.MANUAL_REVIEW),
                ratio(approved.size(), approved.size() + rejected),
                approved.stream().map(LoanApplication::getLatestPd).filter(Objects::nonNull)
                        .mapToDouble(BigDecimal::doubleValue).average().stream().boxed().findFirst().orElse(null),
                ratio(defaults, matured.size()), matured.size(),
                ratio(decided.stream().filter(a -> Boolean.TRUE.equals(a.getDecisionOverride())).count(), decided.size()));

        // Default-rate trend by month of approval
        TreeMap<YearMonth, List<LoanApplication>> byMonth = new TreeMap<>();
        approved.stream().filter(a -> a.getDecidedAt() != null)
                .forEach(a -> byMonth.computeIfAbsent(YearMonth.from(a.getDecidedAt().atZone(ZoneOffset.UTC)),
                        k -> new ArrayList<>()).add(a));
        List<TrendPoint> trend = byMonth.entrySet().stream().map(e -> {
            List<LoanApplication> m = e.getValue();
            long mat = m.stream().filter(a -> a.getOutcome() != null).count();
            long def = m.stream().filter(a -> a.getOutcome() == Outcome.DEFAULTED).count();
            Double avgPd = m.stream().map(LoanApplication::getLatestPd).filter(Objects::nonNull)
                    .mapToDouble(BigDecimal::doubleValue).average().stream().boxed().findFirst().orElse(null);
            return new TrendPoint(e.getKey().toString(), m.size(), mat, def, ratio(def, mat), avgPd);
        }).toList();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("kpis", kpis);
        out.put("statusCounts", byStatus);
        out.put("riskBandCounts", byBand);
        out.put("pdHistogram", histogram);
        out.put("defaultRateTrend", trend);
        try {
            out.put("model", ml.modelInfo());
            out.put("modelHistory", ml.modelHistory());
            out.put("modelServiceAvailable", true);
        } catch (MlUnavailableException e) {
            out.put("modelServiceAvailable", false);
        }
        out.put("circuitBreaker", ml.circuitState().name());
        return out;
    }

    private static Double ratio(long num, long den) {
        return den == 0 ? null : (double) num / den;
    }
}
