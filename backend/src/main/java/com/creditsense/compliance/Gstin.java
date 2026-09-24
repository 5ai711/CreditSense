package com.creditsense.compliance;

import java.util.HashSet;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Goods and Services Tax identification number: structure and check character.
 *
 * <p>Layout: 2-digit state code, 10-character PAN, entity number (1-9, A-Z), the letter Z,
 * and a check character. The check character is a Luhn mod-36 code over the first 14
 * characters: alternate weights 1 and 2, fold each product into base 36 (quotient + remainder),
 * and take (36 - sum mod 36) mod 36. It catches every single-character substitution.
 */
public final class Gstin {

    public static final String ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final Pattern SHAPE = Pattern.compile("^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$");
    public static final Set<String> STATE_CODES = stateCodes();

    private Gstin() {}

    public record Result(boolean valid, String reason, String normalized) {
        static Result ok(String gstin) {
            return new Result(true, "GSTIN structure and check character are valid", gstin);
        }

        static Result fail(String reason, String gstin) {
            return new Result(false, reason, gstin);
        }
    }

    public static String normalize(String raw) {
        return raw == null ? "" : raw.strip().toUpperCase();
    }

    public static char checkCharacter(String first14) {
        int sum = 0;
        for (int i = 0; i < 14; i++) {
            int value = ALPHABET.indexOf(first14.charAt(i));
            if (value < 0) {
                throw new IllegalArgumentException("invalid GSTIN character: " + first14.charAt(i));
            }
            int product = value * (i % 2 == 0 ? 1 : 2);
            sum += product / 36 + product % 36;
        }
        return ALPHABET.charAt((36 - sum % 36) % 36);
    }

    public static Result validate(String raw) {
        String g = normalize(raw);
        if (g.length() != 15) {
            return Result.fail("GSTIN must have exactly 15 characters", g);
        }
        if (!SHAPE.matcher(g).matches()) {
            return Result.fail("GSTIN does not follow the structure: state code, PAN, entity number, 'Z', check character", g);
        }
        if (!STATE_CODES.contains(g.substring(0, 2))) {
            return Result.fail("GSTIN state code " + g.substring(0, 2) + " is not a valid Indian state code", g);
        }
        if (!Pan.isValid(panOf(g))) {
            return Result.fail("The PAN inside the GSTIN is not valid", g);
        }
        char expected = checkCharacter(g.substring(0, 14));
        if (g.charAt(14) != expected) {
            return Result.fail("GSTIN check character is wrong (typing error or fabricated number)", g);
        }
        return Result.ok(g);
    }

    public static boolean hasValidShape(String raw) {
        return SHAPE.matcher(normalize(raw)).matches();
    }

    public static String stateCode(String gstin) {
        return normalize(gstin).substring(0, 2);
    }

    public static String panOf(String gstin) {
        return normalize(gstin).substring(2, 12);
    }

    private static Set<String> stateCodes() {
        Set<String> codes = new HashSet<>();
        for (int i = 1; i <= 38; i++) {
            codes.add(String.format("%02d", i));
        }
        codes.add("97"); // other territory
        return Set.copyOf(codes);
    }
}
