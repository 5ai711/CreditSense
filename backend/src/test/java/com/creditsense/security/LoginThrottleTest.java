package com.creditsense.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;

class LoginThrottleTest {

    /** A clock the test moves by hand. */
    static final class TestClock extends Clock {
        Instant now = Instant.parse("2026-01-01T00:00:00Z");

        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(java.time.ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    final TestClock clock = new TestClock();
    final LoginThrottle throttle = new LoginThrottle(
            new LoginThrottleProperties(3, 5, Duration.ofMinutes(10)), clock);

    @Test
    void blocksAnAccountAfterTooManyFailuresUntilTheWindowPasses() {
        for (int i = 0; i < 3; i++) {
            assertThat(throttle.retryAfter("owner@x.in", "10.0.0.1")).isZero();
            throttle.failed("owner@x.in", "10.0.0.1");
            clock.now = clock.now.plusSeconds(60);
        }
        // the first failure was 3 minutes ago; it leaves the 10-minute window in 7 minutes
        assertThat(throttle.retryAfter("OWNER@x.in ", "10.0.0.2")).isEqualTo(Duration.ofMinutes(7));
        clock.now = clock.now.plus(Duration.ofMinutes(7));
        assertThat(throttle.retryAfter("owner@x.in", "10.0.0.1")).isZero();
    }

    @Test
    void aSuccessfulSignInClearsTheAccountButNotTheClient() {
        for (int i = 0; i < 3; i++) throttle.failed("a@x.in", "10.0.0.9");
        throttle.succeeded("a@x.in");
        assertThat(throttle.retryAfter("a@x.in", "10.0.0.8")).isZero();
        for (int i = 0; i < 2; i++) throttle.failed("b" + i + "@x.in", "10.0.0.9");
        // five failures from one address across different accounts block that address
        assertThat(throttle.retryAfter("c@x.in", "10.0.0.9")).isPositive();
        assertThat(throttle.retryAfter("c@x.in", "10.0.0.7")).isZero();
    }
}
