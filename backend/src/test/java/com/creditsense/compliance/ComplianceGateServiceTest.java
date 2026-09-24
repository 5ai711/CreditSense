package com.creditsense.compliance;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.creditsense.audit.AuditService;
import com.creditsense.common.Actor;
import com.creditsense.common.AppClock;
import com.creditsense.domain.*;
import com.creditsense.repo.*;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class ComplianceGateServiceTest {

    final ApplicantRepository applicants = mock(ApplicantRepository.class);
    final LoanApplicationRepository applications = mock(LoanApplicationRepository.class);
    final BlacklistRepository blacklist = mock(BlacklistRepository.class);
    final ComplianceCheckRepository checks = mock(ComplianceCheckRepository.class);
    final AuditService audit = mock(AuditService.class);
    ComplianceGateService gate;
    LoanApplication app;

    @BeforeEach
    void setUp() {
        gate = new ComplianceGateService(new ComplianceProperties(0.8, 3, 30, 6), applicants, applications, blacklist,
                checks, audit, new AppClock());
        when(blacklist.findFirstByIdentifierTypeAndIdentifier(any(), any())).thenReturn(Optional.empty());
        Applicant a = new Applicant();
        a.setId(7L);
        a.setPan(ComplianceRulesTest.PAN);
        a.setGstin(ComplianceRulesTest.GSTIN);
        a.setUdyamNumber(ComplianceRulesTest.UDYAM);
        a.setStateCode("27");
        app = new LoanApplication();
        app.setId(42L);
        app.setApplicant(a);
        app.setStatus(ApplicationStatus.SUBMITTED);
        app.setSubmittedAt(Instant.now());
        ComplianceRulesTest.completeDocs(12, true).forEach(app::addDocument);
    }

    @Test
    void cleanApplicationClearsTheGateAndStoresOneRowPerRule() {
        ComplianceGateService.Outcome out = gate.evaluate(app, Actor.SYSTEM);

        assertThat(out.passed()).isTrue();
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.COMPLIANCE_REVIEW);
        assertThat(app.getKycScore().doubleValue()).isEqualTo(1.0);
        verify(checks).deleteByApplicationId(42L);
        verify(checks, times(CheckType.values().length)).save(any(ComplianceCheck.class));
        verify(audit).record(eq(Actor.SYSTEM), eq("COMPLIANCE_EVALUATED"), eq("LoanApplication"), eq(42L), any(), any());
    }

    @Test
    void anySingleFailureIsTerminalAndRecordedWithItsReason() {
        when(applicants.countByPanAndIdNot(ComplianceRulesTest.PAN, 7L)).thenReturn(1L);

        ComplianceGateService.Outcome out = gate.evaluate(app, Actor.SYSTEM);

        assertThat(out.passed()).isFalse();
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.COMPLIANCE_FAILED);
        assertThat(out.failures()).extracting(RuleResult::type).containsExactly(CheckType.DUPLICATE_PAN);
        ArgumentCaptor<ComplianceCheck> saved = ArgumentCaptor.forClass(ComplianceCheck.class);
        verify(checks, atLeastOnce()).save(saved.capture());
        assertThat(saved.getAllValues()).filteredOn(c -> !c.isPassed())
                .singleElement().satisfies(c -> assertThat(c.getReason()).contains("other applicant"));
    }

    @Test
    void velocityCountsEarlierApplicationsInTheWindow() {
        when(applications.countByApplicantIdAndSubmittedAtAfterAndIdNot(eq(7L), any(), eq(42L))).thenReturn(3L);
        assertThat(gate.evaluate(app, Actor.SYSTEM).failures()).extracting(RuleResult::type).containsExactly(CheckType.VELOCITY);
    }

    @Test
    void blacklistedPanFails() {
        BlacklistEntry e = new BlacklistEntry();
        e.setIdentifierType(BlacklistEntry.IdentifierType.PAN);
        e.setReason("wilful defaulter");
        when(blacklist.findFirstByIdentifierTypeAndIdentifier(BlacklistEntry.IdentifierType.PAN, ComplianceRulesTest.PAN))
                .thenReturn(Optional.of(e));
        assertThat(gate.evaluate(app, Actor.SYSTEM).failures()).extracting(RuleResult::type).containsExactly(CheckType.BLACKLIST);
    }
}
