package com.creditsense.audit;

import com.creditsense.common.Actor;
import com.creditsense.common.AppClock;
import com.creditsense.domain.AuditLog;
import com.creditsense.repo.AuditLogRepository;
import com.creditsense.security.CurrentUser;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * Writes the append-only audit trail. Entries join the caller's transaction, so a state change
 * and its audit record commit or roll back together.
 */
@Service
public class AuditService {

    private final AuditLogRepository repo;
    private final ObjectMapper mapper;
    private final AppClock clock;

    public AuditService(AuditLogRepository repo, ObjectMapper mapper, AppClock clock) {
        this.repo = repo;
        this.mapper = mapper;
        this.clock = clock;
    }

    @Transactional(propagation = Propagation.REQUIRED)
    public AuditLog record(String action, String entityType, Object entityId, Object before, Object after) {
        return record(CurrentUser.actorOrSystem(), action, entityType, entityId, before, after);
    }

    @Transactional(propagation = Propagation.REQUIRED)
    public AuditLog record(Actor actor, String action, String entityType, Object entityId, Object before, Object after) {
        AuditLog log = new AuditLog();
        log.setActorId(actor.id());
        log.setActorEmail(actor.email());
        log.setActorRole(actor.role());
        log.setAction(action);
        log.setEntityType(entityType);
        log.setEntityId(entityId == null ? null : String.valueOf(entityId));
        log.setBeforeState(before == null ? null : mapper.valueToTree(before));
        log.setAfterState(after == null ? null : mapper.valueToTree(after));
        log.setCreatedAt(clock.now());
        return repo.save(log);
    }
}
