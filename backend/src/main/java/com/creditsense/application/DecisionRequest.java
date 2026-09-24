package com.creditsense.application;

import com.creditsense.domain.Decision;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** A loan officer's decision; the reason is mandatory when overriding the model. */
public record DecisionRequest(@NotNull Decision decision, @Size(max = 1000) String reason) {}
