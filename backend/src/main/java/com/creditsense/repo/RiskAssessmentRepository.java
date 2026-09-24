package com.creditsense.repo;

import com.creditsense.domain.RiskAssessment;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RiskAssessmentRepository extends JpaRepository<RiskAssessment, Long> {
    Optional<RiskAssessment> findFirstByApplicationIdOrderByAssessedAtDescIdDesc(Long applicationId);

    List<RiskAssessment> findByApplicationIdOrderByAssessedAtDesc(Long applicationId);
}
