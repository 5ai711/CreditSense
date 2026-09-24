package com.creditsense.compliance;

import java.util.regex.Pattern;

/** Udyam (MSME) registration number, e.g. UDYAM-TS-02-0012345. */
public final class Udyam {

    private static final Pattern UDYAM = Pattern.compile("^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$");

    private Udyam() {}

    public static boolean isValid(String raw) {
        return raw != null && UDYAM.matcher(raw.strip().toUpperCase()).matches();
    }
}
