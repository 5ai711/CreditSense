package com.creditsense.common;

import java.time.Duration;
import org.springframework.http.HttpStatus;

/** 429 Too Many Requests, with the delay the client should wait (sent as {@code Retry-After}). */
public class RateLimitedException extends ApiException {

    private final Duration retryAfter;

    public RateLimitedException(String message, Duration retryAfter) {
        super(HttpStatus.TOO_MANY_REQUESTS, message);
        this.retryAfter = retryAfter;
    }

    public long retryAfterSeconds() {
        return Math.max(1, (retryAfter.toMillis() + 999) / 1000);
    }
}
