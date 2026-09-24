package com.creditsense.security;

import com.creditsense.common.ApiException;
import com.creditsense.domain.RefreshToken;
import com.creditsense.domain.User;
import com.creditsense.repo.RefreshTokenRepository;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Opaque, rotating refresh tokens. Each refresh revokes the presented token and issues a new
 * one; presenting a revoked token revokes every session of that user (token-theft signal).
 */
@Service
public class RefreshTokenService {

    private final RefreshTokenRepository repo;
    private final JwtProperties props;
    private final SecureRandom random = new SecureRandom();

    public RefreshTokenService(RefreshTokenRepository repo, JwtProperties props) {
        this.repo = repo;
        this.props = props;
    }

    public record Rotated(User user, String refreshToken) {}

    @Transactional
    public String issue(User user) {
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        RefreshToken rt = new RefreshToken();
        rt.setUser(user);
        rt.setTokenHash(hash(token));
        rt.setExpiresAt(Instant.now().plus(props.refreshTokenTtl()));
        repo.save(rt);
        return token;
    }

    @Transactional(noRollbackFor = ApiException.class)
    public Rotated rotate(String presented) {
        RefreshToken rt = repo.findByTokenHash(hash(presented))
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "invalid refresh token"));
        if (rt.isRevoked()) {
            repo.revokeAllForUser(rt.getUser().getId());
            throw new ApiException(HttpStatus.UNAUTHORIZED, "refresh token was already used; all sessions revoked");
        }
        if (rt.getExpiresAt().isBefore(Instant.now()) || !rt.getUser().isEnabled()) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "refresh token expired");
        }
        rt.setRevoked(true);
        return new Rotated(rt.getUser(), issue(rt.getUser()));
    }

    @Transactional
    public void revoke(String presented) {
        repo.findByTokenHash(hash(presented)).ifPresent(rt -> rt.setRevoked(true));
    }

    static String hash(String token) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
