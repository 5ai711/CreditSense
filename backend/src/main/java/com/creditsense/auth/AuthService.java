package com.creditsense.auth;

import com.creditsense.audit.AuditService;
import com.creditsense.auth.AuthDtos.*;
import com.creditsense.common.Actor;
import com.creditsense.common.ApiException;
import com.creditsense.domain.Role;
import com.creditsense.domain.User;
import com.creditsense.repo.UserRepository;
import com.creditsense.security.JwtService;
import com.creditsense.security.RefreshTokenService;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {


    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final JwtService jwt;
    private final RefreshTokenService refreshTokens;
    private final AuditService audit;
    // Compared against when the email is unknown, so response time does not reveal which emails exist.
    private final String dummyHash;

    public AuthService(UserRepository users, PasswordEncoder encoder, JwtService jwt,
            RefreshTokenService refreshTokens, AuditService audit) {
        this.users = users;
        this.encoder = encoder;
        this.jwt = jwt;
        this.refreshTokens = refreshTokens;
        this.audit = audit;
        this.dummyHash = encoder.encode(java.util.UUID.randomUUID().toString());
    }

    /** Self-registration always creates an APPLICANT; staff accounts are provisioned separately. */
    @Transactional
    public TokenResponse register(RegisterRequest req) {
        String email = req.email().strip().toLowerCase();
        if (users.existsByEmailIgnoreCase(email)) {
            throw ApiException.conflict("an account with this email already exists");
        }
        User u = new User();
        u.setEmail(email);
        u.setFullName(req.fullName().strip());
        u.setPasswordHash(encoder.encode(req.password()));
        u.setRole(Role.APPLICANT);
        users.save(u);
        audit.record(Actor.of(u), "USER_REGISTERED", "User", u.getId(), null,
                Map.of("email", email, "role", u.getRole()));
        return tokens(u);
    }

    @Transactional(noRollbackFor = ApiException.class)
    public TokenResponse login(LoginRequest req) {
        String email = req.email().strip().toLowerCase();
        User u = users.findByEmailIgnoreCase(email).orElse(null);
        boolean ok = encoder.matches(req.password(), u == null ? dummyHash : u.getPasswordHash());
        if (u == null || !ok || !u.isEnabled()) {
            audit.record(new Actor(u == null ? null : u.getId(), email, u == null ? "UNKNOWN" : u.getRole().name()),
                    "LOGIN_FAILED", "User", u == null ? null : u.getId(), null, null);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "invalid email or password");
        }
        audit.record(Actor.of(u), "LOGIN_SUCCEEDED", "User", u.getId(), null, null);
        return tokens(u);
    }

    /** noRollbackFor: detecting a reused token must still commit the revocation of every session. */
    @Transactional(noRollbackFor = ApiException.class)
    public TokenResponse refresh(RefreshRequest req) {
        RefreshTokenService.Rotated r = refreshTokens.rotate(req.refreshToken());
        return new TokenResponse(jwt.issueAccessToken(r.user()), r.refreshToken(), "Bearer",
                jwt.accessTokenTtlSeconds(), UserDto.of(r.user()));
    }

    @Transactional
    public void logout(RefreshRequest req) {
        refreshTokens.revoke(req.refreshToken());
    }

    @Transactional(readOnly = true)
    public UserDto me(Long userId) {
        return users.findById(userId).map(UserDto::of).orElseThrow(() -> ApiException.notFound("user"));
    }

    private TokenResponse tokens(User u) {
        return new TokenResponse(jwt.issueAccessToken(u), refreshTokens.issue(u), "Bearer",
                jwt.accessTokenTtlSeconds(), UserDto.of(u));
    }
}
