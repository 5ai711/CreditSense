package com.creditsense.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** {@code secure}: send the cookie over HTTPS only. Off for plain-HTTP local runs, on in the prod profile. */
@ConfigurationProperties("creditsense.auth.refresh-cookie")
public record RefreshCookieProperties(boolean secure) {}
