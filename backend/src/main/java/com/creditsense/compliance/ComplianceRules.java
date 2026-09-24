package com.creditsense.compliance;

import com.creditsense.domain.BlacklistEntry;
import com.creditsense.domain.CheckType;
import com.creditsense.domain.DocumentType;
import com.creditsense.domain.KycDocument;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * The deterministic rules of the compliance gate. Every method is a pure function of its
 * inputs, so each rule can be tested in isolation. Nothing here is learned or fuzzy.
 */
public class ComplianceRules {

    private static final Pattern ADDRESS_PROOF_REF = Pattern.compile("^[A-Z0-9/-]{6,30}$");

    private final ComplianceProperties props;

    public ComplianceRules(ComplianceProperties props) {
        this.props = props;
    }

    /** GSTIN structure, check character, and that the GSTIN belongs to the declared PAN. */
    public RuleResult gstValidity(String gstin, String declaredPan) {
        Gstin.Result r = Gstin.validate(gstin);
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("gstin", r.normalized());
        if (!r.valid()) {
            return RuleResult.fail(CheckType.GST_VALIDITY, r.reason(), details);
        }
        String panInGstin = Gstin.panOf(r.normalized());
        details.put("panInGstin", panInGstin);
        if (!panInGstin.equals(normalize(declaredPan))) {
            return RuleResult.fail(CheckType.GST_VALIDITY,
                    "GSTIN is registered to PAN " + panInGstin + ", not the declared PAN", details);
        }
        return RuleResult.pass(CheckType.GST_VALIDITY, r.reason() + " and match the declared PAN", details);
    }

    public record KycEvaluation(RuleResult result, double score, Map<KycDocument, String> notes) {}

    /**
     * Verifies each submitted document and computes the weighted completeness score.
     * Passing needs every mandatory document verified and the score at or above the threshold.
     */
    public KycEvaluation kyc(List<KycDocument> docs, String pan, String gstin, String udyamNumber) {
        Map<DocumentType, KycDocument> byType = new EnumMap<>(DocumentType.class);
        Map<KycDocument, String> notes = new LinkedHashMap<>();
        double score = 0;
        for (KycDocument doc : docs) {
            String note = verify(doc, pan, gstin, udyamNumber);
            boolean ok = note == null;
            doc.setVerified(ok);
            doc.setVerificationNote(ok ? "verified" : note);
            notes.put(doc, doc.getVerificationNote());
            if (ok && !byType.containsKey(doc.getDocType())) {
                byType.put(doc.getDocType(), doc);
                score += doc.getDocType().weight() * credit(doc);
            }
        }
        List<String> missing = new ArrayList<>();
        for (DocumentType t : DocumentType.values()) {
            if (t.mandatory() && !byType.containsKey(t)) {
                missing.add(label(t));
            }
        }
        score = Math.round(score * 10000) / 10000.0;
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("score", score);
        details.put("threshold", props.kycThreshold());
        details.put("missingOrUnverified", missing);
        RuleResult result;
        if (!missing.isEmpty()) {
            result = RuleResult.fail(CheckType.KYC_COMPLETENESS,
                    "Missing or unverified mandatory documents: " + String.join(", ", missing), details);
        } else if (score + 1e-9 < props.kycThreshold()) {
            result = RuleResult.fail(CheckType.KYC_COMPLETENESS,
                    String.format("KYC completeness %.2f is below the required %.2f", score, props.kycThreshold()), details);
        } else {
            result = RuleResult.pass(CheckType.KYC_COMPLETENESS,
                    String.format("All mandatory documents verified; completeness %.2f", score), details);
        }
        return new KycEvaluation(result, score, notes);
    }

    /** Returns null when the document verifies, otherwise the reason it does not. */
    String verify(KycDocument doc, String pan, String gstin, String udyamNumber) {
        String number = normalize(doc.getDocumentNumber());
        return switch (doc.getDocType()) {
            case PAN -> !Pan.isValid(number) ? "not a valid PAN"
                    : !number.equals(normalize(pan)) ? "PAN card does not match the declared PAN" : null;
            case UDYAM -> !Udyam.isValid(number) ? "not a valid Udyam registration number"
                    : (udyamNumber != null && !udyamNumber.isBlank() && !number.equals(normalize(udyamNumber)))
                            ? "Udyam certificate does not match the declared registration" : null;
            case ADDRESS_PROOF -> ADDRESS_PROOF_REF.matcher(number).matches() ? null : "reference number is not recognisable";
            case BANK_STATEMENT -> {
                Integer months = doc.getMonthsCovered();
                yield months == null || months < props.minBankStatementMonths()
                        ? "statement must cover at least " + props.minBankStatementMonths() + " months" : null;
            }
            case GST_CERTIFICATE -> number.equals(normalize(gstin)) ? null : "certificate GSTIN does not match";
        };
    }

    private double credit(KycDocument doc) {
        if (doc.getDocType() == DocumentType.BANK_STATEMENT) {
            return Math.min(doc.getMonthsCovered(), 12) / 12.0; // a full year earns full credit
        }
        return 1.0;
    }

    public RuleResult duplicatePan(String pan, long otherAccountsWithSamePan) {
        Map<String, Object> details = Map.of("pan", normalize(pan), "otherAccounts", otherAccountsWithSamePan);
        return otherAccountsWithSamePan > 0
                ? RuleResult.fail(CheckType.DUPLICATE_PAN,
                        "PAN is already used by " + otherAccountsWithSamePan + " other applicant account(s)", details)
                : RuleResult.pass(CheckType.DUPLICATE_PAN, "PAN is not used by any other applicant", details);
    }

    /** The declared business address must be in the state where the GSTIN is registered. */
    public RuleResult addressMismatch(String gstin, String declaredStateCode) {
        String g = Gstin.normalize(gstin);
        if (g.length() < 2) {
            return RuleResult.fail(CheckType.ADDRESS_MISMATCH, "No GSTIN to compare the address with", Map.of());
        }
        String registered = g.substring(0, 2);
        Map<String, Object> details = Map.of("gstinState", registered, "declaredState", String.valueOf(declaredStateCode));
        return registered.equals(declaredStateCode)
                ? RuleResult.pass(CheckType.ADDRESS_MISMATCH, "Declared address is in the GST-registered state", details)
                : RuleResult.fail(CheckType.ADDRESS_MISMATCH, "Declared address state " + declaredStateCode
                        + " differs from GST-registered state " + registered, details);
    }

    public RuleResult blacklist(Optional<BlacklistEntry> panHit, Optional<BlacklistEntry> gstinHit) {
        Optional<BlacklistEntry> hit = panHit.or(() -> gstinHit);
        return hit.map(e -> RuleResult.fail(CheckType.BLACKLIST,
                        e.getIdentifierType() + " is on the internal blacklist: " + e.getReason(),
                        Map.<String, Object>of("identifierType", e.getIdentifierType().name())))
                .orElseGet(() -> RuleResult.pass(CheckType.BLACKLIST, "No blacklist match for PAN or GSTIN", Map.of()));
    }

    public RuleResult velocity(long earlierApplicationsInWindow) {
        Map<String, Object> details = Map.of(
                "earlierApplications", earlierApplicationsInWindow,
                "allowed", props.velocityMaxApplications(),
                "windowDays", props.velocityWindowDays());
        return earlierApplicationsInWindow >= props.velocityMaxApplications()
                ? RuleResult.fail(CheckType.VELOCITY, earlierApplicationsInWindow + " earlier applications in the last "
                        + props.velocityWindowDays() + " days (limit " + props.velocityMaxApplications() + ")", details)
                : RuleResult.pass(CheckType.VELOCITY, "Application frequency is within limits", details);
    }

    static String label(DocumentType t) {
        return switch (t) {
            case PAN -> "PAN card";
            case UDYAM -> "Udyam registration";
            case ADDRESS_PROOF -> "address proof";
            case BANK_STATEMENT -> "bank statements";
            case GST_CERTIFICATE -> "GST certificate";
        };
    }

    private static String normalize(String s) {
        return s == null ? "" : s.strip().toUpperCase();
    }
}
