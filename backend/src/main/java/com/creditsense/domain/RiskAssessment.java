package com.creditsense.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import lombok.Getter;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "risk_assessments")
@Getter
@Setter
public class RiskAssessment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "application_id")
    private LoanApplication application;

    @Column(name = "probability_of_default", nullable = false)
    private BigDecimal probabilityOfDefault;

    @Enumerated(EnumType.STRING)
    @Column(name = "risk_band", nullable = false)
    private RiskBand riskBand;

    @Column(name = "model_version", nullable = false)
    private String modelVersion;

    @Column(name = "base_value", nullable = false)
    private double baseValue;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "shap_contributions", nullable = false, columnDefinition = "jsonb")
    private List<ShapContribution> shapContributions;

    /** Exactly what was sent to the model, kept so every score can be reproduced. */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "feature_vector", nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> featureVector;

    @Column(name = "assessed_at", nullable = false)
    private Instant assessedAt = Instant.now();
}
