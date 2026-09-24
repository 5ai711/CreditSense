package com.creditsense.compliance;

import java.util.regex.Pattern;

/** Permanent account number: five letters (fourth is the holder type), four digits, one letter. */
public final class Pan {

    private static final Pattern PAN = Pattern.compile("^[A-Z]{3}[CPHFATBLJG][A-Z][0-9]{4}[A-Z]$");

    private Pan() {}

    public static boolean isValid(String raw) {
        return raw != null && PAN.matcher(raw.strip().toUpperCase()).matches();
    }
}
