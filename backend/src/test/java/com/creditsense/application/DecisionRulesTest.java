package com.creditsense.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

import com.creditsense.audit.AuditService;
import com.creditsense.common.ApiException;
import com.creditsense.common.AppClock;
import com.creditsense.domain.*;
import com.creditsense.repo.*;
import com.creditsense.security.AuthUser;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class DecisionRulesTest {

    final LoanApplicationRepository applications = mock(LoanApplicationRepository.class);
    final UserRepository users = mock(UserRepository.class);
    final AuditService audit = mock(AuditService.class);
    final AuthUser officer = new AuthUser(3L, "officer@x", Role.LOAN_OFFICER);
    LoanApplicationService service;
    LoanApplication app;

    @BeforeEach
    void setUp() {
        service = new LoanApplicationService(applications, mock(ApplicantRepository.class), users,
                mock(ComplianceCheckRepository.class), mock(RiskAssessmentRepository.class),
                mock(AuditLogRepository.class), null, null, new ApplicationAccessPolicy(), audit, new AppClock());
        app = new LoanApplication();
        app.setId(9L);
        app.setStatus(ApplicationStatus.RISK_SCORED);
        app.setModelRecommendation(Decision.APPROVE);
        when(applications.findById(9L)).thenReturn(Optional.of(app));
        when(users.getReferenceById(anyLong())).thenReturn(new User());
    }

    @Test
    void followingTheModelNeedsNoReason() {
        service.decide(9L, officer, new DecisionRequest(Decision.APPROVE, null));
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.APPROVED);
        assertThat(app.getDecisionOverride()).isFalse();
        verify(audit).record(eq(officer.actor()), eq("DECISION_RECORDED"), any(), eq(9L), any(), any());
    }

    @Test
    void overridingTheModelRequiresAReason() {
        assertThatThrownBy(() -> service.decide(9L, officer, new DecisionRequest(Decision.REJECT, "  ")))
                .isInstanceOf(ApiException.class).hasMessageContaining("overriding");
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.RISK_SCORED);

        service.decide(9L, officer, new DecisionRequest(Decision.REJECT, "Recent cheque bounces on the current account"));
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.REJECTED);
        assertThat(app.getDecisionOverride()).isTrue();
    }

    @Test
    void manualReviewDecisionsAlwaysNeedAReason() {
        app.setStatus(ApplicationStatus.MANUAL_REVIEW);
        app.setModelRecommendation(null);
        assertThatThrownBy(() -> service.decide(9L, officer, new DecisionRequest(Decision.APPROVE, null)))
                .hasMessageContaining("without a model score");
    }

    @Test
    void onlyScoredOrManualReviewApplicationsCanBeDecided() {
        app.setStatus(ApplicationStatus.COMPLIANCE_FAILED);
        assertThatThrownBy(() -> service.decide(9L, officer, new DecisionRequest(Decision.APPROVE, "long enough reason")))
                .isInstanceOf(ApiException.class).hasMessageContaining("only risk-scored");
    }
}
