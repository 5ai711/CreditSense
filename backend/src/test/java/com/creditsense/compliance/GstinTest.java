package com.creditsense.compliance;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class GstinTest {

    // Publicly documented sample GSTINs with correct check characters
    private static final String VALID = "27AAPFU0939F1ZV";

    @ParameterizedTest
    @ValueSource(strings = {"27AAPFU0939F1ZV", "29AAGCB7383J1Z4", " 27aapfu0939f1zv "})
    void acceptsValidGstins(String gstin) {
        assertThat(Gstin.validate(gstin).valid()).isTrue();
    }

    @Test
    void computesTheCheckCharacter() {
        assertThat(Gstin.checkCharacter("27AAPFU0939F1Z")).isEqualTo('V');
    }

    @Test
    void detectsEverySingleCharacterSubstitution() {
        for (int pos = 0; pos < 15; pos++) {
            for (char c : Gstin.ALPHABET.toCharArray()) {
                if (c == VALID.charAt(pos)) continue;
                String mutated = VALID.substring(0, pos) + c + VALID.substring(pos + 1);
                assertThat(Gstin.validate(mutated).valid())
                        .as("substituting %s at position %d", c, pos).isFalse();
            }
        }
    }

    @Test
    void detectsAdjacentTransposition() {
        String swapped = "27AAPFU0993F1ZV"; // "39" -> "93"
        assertThat(Gstin.validate(swapped).valid()).isFalse();
    }

    @Test
    void explainsWhyAGstinIsInvalid() {
        assertThat(Gstin.validate("27AAPFU0939F1Z").reason()).contains("15 characters");
        assertThat(Gstin.validate("27AAPFU0939F1YV").reason()).contains("structure");
        assertThat(Gstin.validate("99AAPFU0939F1ZV").reason()).contains("state code");
        assertThat(Gstin.validate("27AAPXU0939F1ZV").reason()).contains("PAN");
        assertThat(Gstin.validate("27AAPFU0939F1ZW").reason()).contains("check character");
        assertThat(Gstin.validate(null).valid()).isFalse();
    }

    @Test
    void formatCheckIgnoresTheChecksum() {
        assertThat(Gstin.hasValidShape("27AAPFU0939F1ZW")).isTrue(); // wrong check char, right shape
        assertThat(Gstin.hasValidShape("27AAPFU0939F1YV")).isFalse();
    }

    @Test
    void extractsStateAndPan() {
        assertThat(Gstin.stateCode(VALID)).isEqualTo("27");
        assertThat(Gstin.panOf(VALID)).isEqualTo("AAPFU0939F");
    }
}
