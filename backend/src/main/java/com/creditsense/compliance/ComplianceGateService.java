package com.creditsense.compliance;

import com.creditsense.audit.AuditService;
import com.creditsense.common.Actor;
import com.creditsense.common.AppClock;
import com.creditsense.domain.Applicant;
import com.creditsense.domain.ApplicationStatus;
import com.creditsense.domain.BlacklistEntry.IdentifierType;
import com.creditsense.domain.ComplianceCheck;
import com.creditsense.domain.LoanApplication;
import com.creditsense.repo.ApplicantRepository;
import com.creditsense.repo.BlacklistRepository;
import com.creditsense.repo.ComplianceCheckRepository;
import com.creditsense.repo.LoanApplicationRepository;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Runs every rule of the compliance gate for an application, stores one result row per rule,
 * and moves the application to COMPLIANCE_REVIEW (cleared, awaiting scoring) or the terminal
 * COMPLIANCE_FAILED state. The ML model is never consulted here.
 */
@Service
public class ComplianceGateService {

    public record Outcome(boolean passed, List<RuleResult> results, double kycScore) {
        public List<RuleResult> failures() {
            return results.stream().filter(r -> !r.passed()).toList();
        }
    }

    private final ComplianceRules rules;
    private final ComplianceProperties props;
    private final ApplicantRepository applicants;
    private final LoanApplicationRepository applications;
    private final BlacklistRepository blacklist;
    private final ComplianceCheckRepository checks;
    private final AuditService audit;
    private final AppClock clock;

    public ComplianceGateService(ComplianceProperties props, ApplicantRepository applicants,
            LoanApplicationRepository applications, BlacklistRepository blacklist, ComplianceCheckRepository checks,
            AuditService audit, AppClock clock) {
        this.rules = new ComplianceRules(props);
        this.props = props;
        this.applicants = applicants;
        this.applications = applications;
        this.blacklist = blacklist;
        this.checks = checks;
        this.audit = audit;
        this.clock = clock;
    }

    @Transactional
    public Outcome evaluate(LoanApplication app, Actor actor) {
        ApplicationStatus before = app.getStatus();
        Applicant a = app.getApplicant();
        String pan = a.getPan();
        String gstin = Gstin.normalize(a.getGstin());

        List<RuleResult> results = new ArrayList<>();
        results.add(rules.gstValidity(gstin, pan));
        ComplianceRules.KycEvaluation kyc = rules.kyc(app.getDocuments(), pan, gstin, a.getUdyamNumber());
        results.add(kyc.result());
        results.add(rules.duplicatePan(pan, applicants.countByPanAndIdNot(pan, a.getId())));
        results.add(rules.addressMismatch(gstin, a.getStateCode()));
        results.add(rules.blacklist(
                blacklist.findFirstByIdentifierTypeAndIdentifier(IdentifierType.PAN, pan),
                blacklist.findFirstByIdentifierTypeAndIdentifier(IdentifierType.GSTIN, gstin)));
        Instant windowStart = app.getSubmittedAt().minus(Duration.ofDays(props.velocityWindowDays()));
        results.add(rules.velocity(applications.countByApplicantIdAndSubmittedAtAfterAndIdNot(
                a.getId(), windowStart, app.getId())));

        checks.deleteByApplicationId(app.getId());
        Instant now = clock.now();
        for (RuleResult r : results) {
            ComplianceCheck c = new ComplianceCheck();
            c.setApplication(app);
            c.setCheckType(r.type());
            c.setCategory(r.type().category());
            c.setPassed(r.passed());
            c.setReason(r.reason());
            c.setDetails(r.details());
            c.setEvaluatedAt(now);
            checks.save(c);
        }

        boolean passed = results.stream().allMatch(RuleResult::passed);
        app.setKycScore(BigDecimal.valueOf(kyc.score()).setScale(4, RoundingMode.HALF_UP));
        app.setStatus(passed ? ApplicationStatus.COMPLIANCE_REVIEW : ApplicationStatus.COMPLIANCE_FAILED);

        Map<String, Object> after = new LinkedHashMap<>();
        after.put("status", app.getStatus());
        after.put("kycScore", kyc.score());
        after.put("failedChecks", results.stream().filter(r -> !r.passed())
                .map(r -> Map.of("check", r.type().name(), "reason", r.reason())).toList());
        audit.record(actor, "COMPLIANCE_EVALUATED", "LoanApplication", app.getId(), Map.of("status", before), after);
        return new Outcome(passed, results, kyc.score());
    }
}
