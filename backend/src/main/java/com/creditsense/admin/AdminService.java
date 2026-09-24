package com.creditsense.admin;

import com.creditsense.audit.AuditService;
import com.creditsense.common.AppClock;
import com.creditsense.domain.ApplicationStatus;
import com.creditsense.domain.LoanApplication;
import com.creditsense.domain.Outcome;
import com.creditsense.repo.LoanApplicationRepository;
import com.creditsense.repo.RiskAssessmentRepository;
import com.creditsense.risk.MlClient;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** The feedback loop: simulate matured-loan outcomes, then retrain champion vs challenger. */
@Service
public class AdminService {

    public record MaturityResult(int matured, int defaulted, int skippedWithoutScore) {}

    private final LoanApplicationRepository applications;
    private final RiskAssessmentRepository assessments;
    private final MlClient ml;
    private final AuditService audit;
    private final AppClock clock;

    public AdminService(LoanApplicationRepository applications, RiskAssessmentRepository assessments, MlClient ml,
            AuditService audit, AppClock clock) {
        this.applications = applications;
        this.assessments = assessments;
        this.ml = ml;
        this.audit = audit;
        this.clock = clock;
    }

    /**
     * Pretends time has passed for approved loans decided at least {@code minAgeDays} ago: the ML
     * service draws each loan's 12-month outcome from the ground-truth process and stores it as
     * training feedback. The exact feature vector that was scored is sent, not a recomputation.
     */
    @Transactional
    public MaturityResult simulateMaturity(int minAgeDays) {
        List<LoanApplication> due = applications.findByStatusAndOutcomeIsNullAndDecidedAtBefore(
                ApplicationStatus.APPROVED, clock.now().minus(Duration.ofDays(Math.max(0, minAgeDays))).plusSeconds(1));
        List<MlClient.OutcomeItem> items = new ArrayList<>();
        Map<String, LoanApplication> byRef = new LinkedHashMap<>();
        int skipped = 0;
        for (LoanApplication app : due) {
            var ra = assessments.findFirstByApplicationIdOrderByAssessedAtDescIdDesc(app.getId());
            if (ra.isEmpty()) { // approved from manual review without a score: nothing to learn from
                skipped++;
                continue;
            }
            items.add(new MlClient.OutcomeItem(app.getReference(), ra.get().getFeatureVector()));
            byRef.put(app.getReference(), app);
        }
        if (items.isEmpty()) {
            return new MaturityResult(0, 0, skipped);
        }
        Map<String, Boolean> outcomes = ml.simulateOutcomes(items).stream()
                .collect(Collectors.toMap(MlClient.OutcomeResult::reference_id, MlClient.OutcomeResult::defaulted,
                        (a, b) -> a));
        int defaulted = 0;
        for (var e : byRef.entrySet()) {
            Boolean d = outcomes.get(e.getKey());
            if (d == null) continue;
            LoanApplication app = e.getValue();
            app.setOutcome(d ? Outcome.DEFAULTED : Outcome.REPAID);
            app.setOutcomeRecordedAt(clock.now());
            if (d) defaulted++;
            audit.record("LOAN_OUTCOME_RECORDED", "LoanApplication", app.getId(), Map.of("outcome", "PENDING"),
                    Map.of("outcome", app.getOutcome()));
        }
        MaturityResult result = new MaturityResult(byRef.size(), defaulted, skipped);
        audit.record("OUTCOMES_SIMULATED", "Portfolio", null, null, result);
        return result;
    }

    @Transactional
    public JsonNode retrain() {
        JsonNode result = ml.retrain();
        Map<String, Object> summary = new LinkedHashMap<>();
        for (String k : List.of("champion_version", "challenger_version", "champion_holdout_auc",
                "challenger_holdout_auc", "promoted", "serving_version", "feedback_rows", "holdout_rows")) {
            JsonNode v = result.get(k);
            summary.put(k, v == null || v.isNull() ? null : v.isNumber() ? v.numberValue() : v.isBoolean() ? v.booleanValue() : v.asText());
        }
        audit.record("MODEL_RETRAINED", "Model", summary.get("challenger_version"), null, summary);
        return result;
    }

    public Map<String, Object> model() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("info", ml.modelInfo());
        out.put("history", ml.modelHistory());
        out.put("circuitBreaker", ml.circuitState().name());
        return out;
    }

}
