package com.creditsense.risk;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.creditsense.audit.AuditService;
import com.creditsense.common.Actor;
import com.creditsense.common.ApiException;
import com.creditsense.common.AppClock;
import com.creditsense.domain.*;
import com.creditsense.repo.RiskAssessmentRepository;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class RiskAssessmentServiceTest {

    final MlClient ml = mock(MlClient.class);
    final RiskAssessmentRepository repo = mock(RiskAssessmentRepository.class);
    final AuditService audit = mock(AuditService.class);
    RiskAssessmentService service;
    LoanApplication app;

    @BeforeEach
    void setUp() {
        service = new RiskAssessmentService(ml, new ExplanationContract(), new FeatureVectorBuilder(), repo, audit,
                new MlProperties("http://ml", null, null, 0.20), new AppClock());
        app = FeatureVectorBuilderTest.sample();
        app.setId(5L);
        app.setStatus(ApplicationStatus.COMPLIANCE_REVIEW);
    }

    @Test
    void persistsScoreWithItsLedgerAndRecommends() {
        when(ml.predict(anyMap())).thenReturn(TestPredictions.additive(0.08, "MEDIUM", null));

        RiskAssessmentService.Result r = service.assess(app, Actor.SYSTEM);

        assertThat(r.scored()).isTrue();
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.RISK_SCORED);
        assertThat(app.getLatestRiskBand()).isEqualTo(RiskBand.MEDIUM);
        assertThat(app.getModelRecommendation()).isEqualTo(Decision.APPROVE);
        assertThat(r.assessment().getShapContributions()).hasSize(13);
        assertThat(r.assessment().getFeatureVector()).containsKey("revenue_volatility");
        verify(repo).save(any(RiskAssessment.class));
        verify(audit).record(eq(Actor.SYSTEM), eq("RISK_ASSESSED"), any(), eq(5L), any(), any());
    }

    @Test
    void recommendsRejectionForHighRisk() {
        when(ml.predict(anyMap())).thenReturn(TestPredictions.additive(0.31, "HIGH", null));
        service.assess(app, Actor.SYSTEM);
        assertThat(app.getModelRecommendation()).isEqualTo(Decision.REJECT);
    }

    @Test
    void unavailableModelRoutesToManualReview() {
        when(ml.predict(anyMap())).thenThrow(new MlUnavailableException("ML service unavailable (timed out)", null));

        RiskAssessmentService.Result r = service.assess(app, Actor.SYSTEM);

        assertThat(r.scored()).isFalse();
        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.MANUAL_REVIEW);
        assertThat(app.getManualReviewReason()).contains("timed out");
        verify(repo, never()).save(any());
        verify(audit).record(eq(Actor.SYSTEM), eq("ROUTED_TO_MANUAL_REVIEW"), any(), eq(5L), any(), any());
    }

    @Test
    void scoreWithoutValidExplanationIsNeverStored() {
        when(ml.predict(anyMap())).thenReturn(new MlPrediction(0.08, "MEDIUM", "v1", -2, List.of()));

        service.assess(app, Actor.SYSTEM);

        assertThat(app.getStatus()).isEqualTo(ApplicationStatus.MANUAL_REVIEW);
        assertThat(app.getManualReviewReason()).startsWith("Score rejected");
        assertThat(app.getLatestPd()).isNull();
        verify(repo, never()).save(any());
    }

    @Test
    void complianceFailedApplicationsCannotBeScored() {
        app.setStatus(ApplicationStatus.COMPLIANCE_FAILED);
        assertThatThrownBy(() -> service.assess(app, Actor.SYSTEM)).isInstanceOf(ApiException.class)
                .hasMessageContaining("compliance gate");
        verifyNoInteractions(ml);
    }
}
