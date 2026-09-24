package com.creditsense.repo;

import com.creditsense.domain.ComplianceCheck;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

public interface ComplianceCheckRepository extends JpaRepository<ComplianceCheck, Long> {
    List<ComplianceCheck> findByApplicationIdOrderByIdAsc(Long applicationId);

    @Modifying
    @Query("delete from ComplianceCheck c where c.application.id = :applicationId")
    void deleteByApplicationId(Long applicationId);
}
