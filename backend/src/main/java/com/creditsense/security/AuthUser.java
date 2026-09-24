package com.creditsense.security;

import com.creditsense.common.Actor;
import com.creditsense.domain.Role;

/** The authenticated principal, rebuilt from a verified access token on every request. */
public record AuthUser(Long id, String email, Role role) {

    public Actor actor() {
        return new Actor(id, email, role.name());
    }

    public boolean isStaff() {
        return role == Role.LOAN_OFFICER || role == Role.ADMIN;
    }
}
