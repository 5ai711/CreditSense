package com.creditsense.compliance;

import jakarta.validation.Constraint;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import jakarta.validation.Payload;
import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Bean Validation for the GSTIN <em>format</em> (15 characters in the right positions).
 *
 * <p>The check character, state code and PAN consistency are deliberately left to the
 * compliance gate: a well-formed but invalid GSTIN is a regulatory finding that must be
 * recorded and explained as COMPLIANCE_FAILED, not a malformed request.
 */
@Documented
@Constraint(validatedBy = GstinFormat.Validator.class)
@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.RECORD_COMPONENT})
@Retention(RetentionPolicy.RUNTIME)
public @interface GstinFormat {
    String message() default "GSTIN must be 15 characters: 2-digit state code, PAN, entity number, 'Z', check character";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};

    class Validator implements ConstraintValidator<GstinFormat, String> {
        @Override
        public boolean isValid(String value, ConstraintValidatorContext ctx) {
            return value == null || Gstin.hasValidShape(value);
        }
    }
}
