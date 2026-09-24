package com.creditsense.compliance;

import com.creditsense.domain.CheckType;
import java.util.Map;

public record RuleResult(CheckType type, boolean passed, String reason, Map<String, Object> details) {

    public static RuleResult pass(CheckType type, String reason, Map<String, Object> details) {
        return new RuleResult(type, true, reason, details);
    }

    public static RuleResult fail(CheckType type, String reason, Map<String, Object> details) {
        return new RuleResult(type, false, reason, details);
    }
}
