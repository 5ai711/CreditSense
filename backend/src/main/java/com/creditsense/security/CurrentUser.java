package com.creditsense.security;

import com.creditsense.common.Actor;
import java.util.Optional;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

public final class CurrentUser {

    private CurrentUser() {}

    public static Optional<AuthUser> get() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        return auth != null && auth.getPrincipal() instanceof AuthUser u ? Optional.of(u) : Optional.empty();
    }

    public static Actor actorOrSystem() {
        return get().map(AuthUser::actor).orElse(Actor.SYSTEM);
    }
}
