package com.creditsense.common;

import com.creditsense.domain.User;

/** Who performed an action, as written to the audit log. */
public record Actor(Long id, String email, String role) {

    public static final Actor SYSTEM = new Actor(null, "system@creditsense", "SYSTEM");

    public static Actor of(User user) {
        return new Actor(user.getId(), user.getEmail(), user.getRole().name());
    }
}
