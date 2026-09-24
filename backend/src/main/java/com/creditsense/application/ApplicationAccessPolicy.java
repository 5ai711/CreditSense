package com.creditsense.application;

import com.creditsense.domain.LoanApplication;
import com.creditsense.security.AuthUser;
import org.springframework.stereotype.Component;

/**
 * Ownership rule: staff can read every application; an applicant can read only their own.
 * Callers turn a denial into 404 so application IDs cannot be probed.
 */
@Component
public class ApplicationAccessPolicy {

    public boolean canView(AuthUser user, LoanApplication app) {
        return user.isStaff() || app.getApplicant().getUser().getId().equals(user.id());
    }
}
