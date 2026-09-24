package com.creditsense.security;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("creditsense.login-throttle")
public record LoginThrottleProperties(int maxFailuresPerAccount, int maxFailuresPerClient, Duration window) {

    public LoginThrottleProperties {
        if (maxFailuresPerAccount <= 0) maxFailuresPerAccount = 5;
        if (maxFailuresPerClient <= 0) maxFailuresPerClient = 20;
        if (window == null) window = Duration.ofMinutes(15);
    }
}
