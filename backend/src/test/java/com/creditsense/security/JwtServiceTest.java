package com.creditsense.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.creditsense.domain.Role;
import com.creditsense.domain.User;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class JwtServiceTest {

    final JwtProperties props = new JwtProperties("test-secret-that-is-long-enough-for-hs256!", "creditsense",
            Duration.ofMinutes(5), Duration.ofDays(1));
    final JwtService jwt = new JwtService(props);

    static User user() {
        User u = new User();
        u.setId(11L);
        u.setEmail("a@b.c");
        u.setRole(Role.LOAN_OFFICER);
        return u;
    }

    @Test
    void roundTripsIdentityAndRole() {
        AuthUser u = jwt.verify(jwt.issueAccessToken(user())).orElseThrow();
        assertThat(u.id()).isEqualTo(11L);
        assertThat(u.role()).isEqualTo(Role.LOAN_OFFICER);
    }

    @Test
    void rejectsTamperedAndForeignTokens() {
        String token = jwt.issueAccessToken(user());
        String tampered = token.substring(0, token.length() - 3) + (token.endsWith("A") ? "BBB" : "AAA");
        assertThat(jwt.verify(tampered)).isEmpty();
        JwtService other = new JwtService(new JwtProperties("another-secret-that-is-long-enough-hs256!!", "creditsense",
                Duration.ofMinutes(5), Duration.ofDays(1)));
        assertThat(jwt.verify(other.issueAccessToken(user()))).isEmpty();
        assertThat(jwt.verify("not-a-jwt")).isEmpty();
    }

    @Test
    void rejectsExpiredTokens() {
        JwtService shortLived = new JwtService(new JwtProperties(props.secret(), "creditsense", Duration.ofSeconds(-1),
                Duration.ofDays(1)));
        assertThat(shortLived.verify(shortLived.issueAccessToken(user()))).isEmpty();
    }

    @Test
    void refusesWeakSecrets() {
        assertThatThrownBy(() -> new JwtProperties("short", "x", null, null)).isInstanceOf(IllegalStateException.class);
    }
}
