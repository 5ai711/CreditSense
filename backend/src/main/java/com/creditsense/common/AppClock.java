package com.creditsense.common;

import java.time.Instant;
import java.util.function.Supplier;
import org.springframework.stereotype.Component;

/**
 * Source of "now" for business timestamps. The demo seeder can shift time for the current
 * thread so that historical demo applications carry consistent dates across tables.
 */
@Component
public class AppClock {

    private static final ThreadLocal<Instant> OVERRIDE = new ThreadLocal<>();

    public Instant now() {
        Instant o = OVERRIDE.get();
        return o != null ? o : Instant.now();
    }

    public <T> T at(Instant when, Supplier<T> work) {
        Instant previous = OVERRIDE.get();
        OVERRIDE.set(when);
        try {
            return work.get();
        } finally {
            if (previous == null) OVERRIDE.remove(); else OVERRIDE.set(previous);
        }
    }
}
