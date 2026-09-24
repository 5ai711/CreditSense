package com.creditsense.audit;

import com.creditsense.domain.AuditLog;
import com.creditsense.repo.AuditLogRepository;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.criteria.Predicate;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuditQueryService {

    public record Entry(Long id, Instant createdAt, Long actorId, String actorEmail, String actorRole, String action,
            String entityType, String entityId, JsonNode beforeState, JsonNode afterState) {

        static Entry of(AuditLog l) {
            return new Entry(l.getId(), l.getCreatedAt(), l.getActorId(), l.getActorEmail(), l.getActorRole(),
                    l.getAction(), l.getEntityType(), l.getEntityId(), l.getBeforeState(), l.getAfterState());
        }
    }

    private final AuditLogRepository repo;

    public AuditQueryService(AuditLogRepository repo) {
        this.repo = repo;
    }

    @Transactional(readOnly = true)
    public Page<Entry> search(String action, String entityType, String entityId, String actor, Instant from,
            Instant to, String q, Pageable pageable) {
        Specification<AuditLog> spec = (root, query, cb) -> {
            List<Predicate> p = new ArrayList<>();
            if (notBlank(action)) p.add(cb.equal(root.get("action"), action.strip().toUpperCase()));
            if (notBlank(entityType)) p.add(cb.equal(root.get("entityType"), entityType.strip()));
            if (notBlank(entityId)) p.add(cb.equal(root.get("entityId"), entityId.strip()));
            if (notBlank(actor)) p.add(cb.like(cb.lower(root.get("actorEmail")), "%" + actor.strip().toLowerCase() + "%"));
            if (from != null) p.add(cb.greaterThanOrEqualTo(root.get("createdAt"), from));
            if (to != null) p.add(cb.lessThan(root.get("createdAt"), to));
            if (notBlank(q)) {
                String like = "%" + q.strip().toLowerCase() + "%";
                p.add(cb.or(cb.like(cb.lower(root.get("action")), like), cb.like(cb.lower(root.get("actorEmail")), like),
                        cb.like(cb.lower(root.get("entityType")), like), cb.like(cb.lower(root.get("entityId")), like)));
            }
            return cb.and(p.toArray(Predicate[]::new));
        };
        return repo.findAll(spec, pageable).map(Entry::of);
    }

    private static boolean notBlank(String s) {
        return s != null && !s.isBlank();
    }
}
