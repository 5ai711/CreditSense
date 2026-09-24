package com.creditsense.security;

import java.time.Clock;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Slows down password guessing: too many failed sign-ins for one account, or from one client address,
 * within a sliding window block further attempts until the oldest failure leaves the window.
 * State is in memory, so each backend instance counts on its own.
 */
@Component
public class LoginThrottle {

    private static final int MAX_TRACKED_KEYS = 100_000;

    private final LoginThrottleProperties props;
    private final Clock clock;
    private final Map<String, Deque<Long>> failures = new ConcurrentHashMap<>();

    @Autowired
    public LoginThrottle(LoginThrottleProperties props) {
        this(props, Clock.systemUTC());
    }

    LoginThrottle(LoginThrottleProperties props, Clock clock) {
        this.props = props;
        this.clock = clock;
    }

    /** How long the caller must wait before trying again, or {@link Duration#ZERO} if it may try now. */
    public Duration retryAfter(String email, String client) {
        long now = clock.millis();
        Duration account = wait(accountKey(email), props.maxFailuresPerAccount(), now);
        Duration address = wait(clientKey(client), props.maxFailuresPerClient(), now);
        return account.compareTo(address) >= 0 ? account : address;
    }

    public void failed(String email, String client) {
        long now = clock.millis();
        if (failures.size() > MAX_TRACKED_KEYS) {
            failures.entrySet().removeIf(e -> expired(e.getValue(), now));
        }
        record(accountKey(email), now);
        record(clientKey(client), now);
    }

    /** A correct password clears the account's count; the client address keeps its history. */
    public void succeeded(String email) {
        failures.remove(accountKey(email));
    }

    private Duration wait(String key, int limit, long now) {
        Deque<Long> times = failures.get(key);
        if (times == null) return Duration.ZERO;
        synchronized (times) {
            prune(times, now);
            if (times.size() < limit) return Duration.ZERO;
            long freeAt = times.peekFirst() + props.window().toMillis();
            return Duration.ofMillis(Math.max(1000, freeAt - now));
        }
    }

    private void record(String key, long now) {
        Deque<Long> times = failures.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (times) {
            prune(times, now);
            times.addLast(now);
        }
    }

    private void prune(Deque<Long> times, long now) {
        long cutoff = now - props.window().toMillis();
        while (!times.isEmpty() && times.peekFirst() <= cutoff) times.pollFirst();
    }

    private boolean expired(Deque<Long> times, long now) {
        synchronized (times) {
            prune(times, now);
            return times.isEmpty();
        }
    }

    private static String accountKey(String email) {
        return "a:" + (email == null ? "" : email.strip().toLowerCase());
    }

    private static String clientKey(String client) {
        return "c:" + (client == null ? "unknown" : client);
    }
}
