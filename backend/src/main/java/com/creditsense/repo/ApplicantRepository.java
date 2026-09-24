package com.creditsense.repo;

import com.creditsense.domain.Applicant;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ApplicantRepository extends JpaRepository<Applicant, Long> {
    Optional<Applicant> findByUserId(Long userId);

    /** Other applicant accounts registered with the same PAN. */
    long countByPanAndIdNot(String pan, Long id);
}
