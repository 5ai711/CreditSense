package com.creditsense.compliance;

import static org.assertj.core.api.Assertions.assertThat;

import com.creditsense.domain.BlacklistEntry;
import com.creditsense.domain.CheckType;
import com.creditsense.domain.DocumentType;
import com.creditsense.domain.KycDocument;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

class ComplianceRulesTest {

    static final String PAN = "AAPFU0939F";
    static final String GSTIN = "27AAPFU0939F1ZV";
    static final String UDYAM = "UDYAM-MH-26-0012345";

    final ComplianceRules rules = new ComplianceRules(new ComplianceProperties(0.8, 3, 30, 6));

    static KycDocument doc(DocumentType type, String number, Integer months) {
        KycDocument d = new KycDocument();
        d.setDocType(type);
        d.setDocumentNumber(number);
        d.setMonthsCovered(months);
        return d;
    }

    static List<KycDocument> completeDocs(int bankMonths, boolean gstCertificate) {
        List<KycDocument> docs = new ArrayList<>(List.of(
                doc(DocumentType.PAN, PAN, null),
                doc(DocumentType.UDYAM, UDYAM, null),
                doc(DocumentType.ADDRESS_PROOF, "EB-1234567", null),
                doc(DocumentType.BANK_STATEMENT, "STMT-1", bankMonths)));
        if (gstCertificate) docs.add(doc(DocumentType.GST_CERTIFICATE, GSTIN, null));
        return docs;
    }

    @Nested
    class GstValidity {
        @Test
        void passesForValidGstinOfTheDeclaredPan() {
            assertThat(rules.gstValidity(GSTIN, PAN).passed()).isTrue();
        }

        @Test
        void failsWhenGstinBelongsToAnotherPan() {
            RuleResult r = rules.gstValidity(GSTIN, "AAPFU0939G");
            assertThat(r.passed()).isFalse();
            assertThat(r.reason()).contains("registered to PAN AAPFU0939F");
        }

        @Test
        void failsOnWrongCheckCharacter() {
            RuleResult r = rules.gstValidity("27AAPFU0939F1ZW", PAN);
            assertThat(r.passed()).isFalse();
            assertThat(r.type()).isEqualTo(CheckType.GST_VALIDITY);
        }
    }

    @Nested
    class Kyc {
        @Test
        void fullSetWithAYearOfStatementsScoresOne() {
            var e = rules.kyc(completeDocs(12, true), PAN, GSTIN, UDYAM);
            assertThat(e.result().passed()).isTrue();
            assertThat(e.score()).isEqualTo(1.0);
        }

        @Test
        void sixMonthsOfStatementsWithoutGstCertificateSitsExactlyOnTheThreshold() {
            var e = rules.kyc(completeDocs(6, false), PAN, GSTIN, UDYAM);
            assertThat(e.score()).isEqualTo(0.8);
            assertThat(e.result().passed()).isTrue();
        }

        @Test
        void shortBankStatementIsNotVerifiedAndBlocksTheApplication() {
            var e = rules.kyc(completeDocs(3, true), PAN, GSTIN, UDYAM);
            assertThat(e.result().passed()).isFalse();
            assertThat(e.result().reason()).contains("bank statements");
        }

        @Test
        void missingMandatoryDocumentFails() {
            List<KycDocument> docs = completeDocs(12, true);
            docs.removeIf(d -> d.getDocType() == DocumentType.UDYAM);
            var e = rules.kyc(docs, PAN, GSTIN, UDYAM);
            assertThat(e.result().passed()).isFalse();
            assertThat(e.result().reason()).contains("Udyam registration");
        }

        @Test
        void panCardMustMatchTheDeclaredPan() {
            List<KycDocument> docs = completeDocs(12, true);
            docs.set(0, doc(DocumentType.PAN, "ABCPE1234F", null));
            var e = rules.kyc(docs, PAN, GSTIN, UDYAM);
            assertThat(e.result().passed()).isFalse();
            assertThat(docs.get(0).getVerificationNote()).contains("does not match");
        }

        @Test
        void malformedDocumentNumbersAreNotVerified() {
            List<KycDocument> docs = completeDocs(12, true);
            docs.set(1, doc(DocumentType.UDYAM, "UDYAM-12345", null));
            docs.set(2, doc(DocumentType.ADDRESS_PROOF, "x", null));
            var e = rules.kyc(docs, PAN, GSTIN, UDYAM);
            assertThat(e.result().passed()).isFalse();
            assertThat(docs.get(1).isVerified()).isFalse();
            assertThat(docs.get(2).isVerified()).isFalse();
        }

        @Test
        void duplicateDocumentsAreCountedOnce() {
            List<KycDocument> docs = completeDocs(12, true);
            docs.add(doc(DocumentType.PAN, PAN, null));
            assertThat(rules.kyc(docs, PAN, GSTIN, UDYAM).score()).isEqualTo(1.0);
        }

        @Test
        void aHigherThresholdCanFailACompleteButMinimalSet() {
            ComplianceRules strict = new ComplianceRules(new ComplianceProperties(0.9, 3, 30, 6));
            var e = strict.kyc(completeDocs(6, false), PAN, GSTIN, UDYAM);
            assertThat(e.result().passed()).isFalse();
            assertThat(e.result().reason()).contains("below the required");
        }
    }

    @Nested
    class Fraud {
        @Test
        void duplicatePan() {
            assertThat(rules.duplicatePan(PAN, 0).passed()).isTrue();
            assertThat(rules.duplicatePan(PAN, 2).reason()).contains("2 other applicant");
        }

        @Test
        void addressMustBeInTheGstRegisteredState() {
            assertThat(rules.addressMismatch(GSTIN, "27").passed()).isTrue();
            RuleResult r = rules.addressMismatch(GSTIN, "36");
            assertThat(r.passed()).isFalse();
            assertThat(r.reason()).contains("36").contains("27");
        }

        @Test
        void blacklistMatchOnPanOrGstin() {
            BlacklistEntry e = new BlacklistEntry();
            e.setIdentifierType(BlacklistEntry.IdentifierType.GSTIN);
            e.setReason("fake invoicing");
            assertThat(rules.blacklist(Optional.empty(), Optional.empty()).passed()).isTrue();
            RuleResult r = rules.blacklist(Optional.empty(), Optional.of(e));
            assertThat(r.passed()).isFalse();
            assertThat(r.reason()).contains("GSTIN").contains("fake invoicing");
        }

        @Test
        void velocityBoundary() {
            assertThat(rules.velocity(2).passed()).isTrue();  // third application in the window
            assertThat(rules.velocity(3).passed()).isFalse(); // fourth
        }
    }
}
