package com.creditsense.repo;

import com.creditsense.domain.BlacklistEntry;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BlacklistRepository extends JpaRepository<BlacklistEntry, Long> {
    Optional<BlacklistEntry> findFirstByIdentifierTypeAndIdentifier(BlacklistEntry.IdentifierType type, String identifier);
}
