package com.creditsense.web;

import com.creditsense.admin.AdminService;
import com.fasterxml.jackson.databind.JsonNode;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.Map;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/admin")
@PreAuthorize("hasRole('ADMIN')")
@Tag(name = "Model lifecycle")
public class AdminController {

    private final AdminService admin;

    public AdminController(AdminService admin) {
        this.admin = admin;
    }

    @PostMapping("/simulate-maturity")
    @Operation(summary = "Simulate 12-month outcomes for approved loans and feed them back as training data")
    public AdminService.MaturityResult simulateMaturity(@RequestParam(defaultValue = "0") int minAgeDays) {
        return admin.simulateMaturity(minAgeDays);
    }

    @PostMapping("/retrain")
    @Operation(summary = "Train a challenger; it replaces the champion only if it wins on held-out AUC")
    public JsonNode retrain() {
        return admin.retrain();
    }

    @GetMapping("/model")
    @Operation(summary = "Serving model details and the champion/challenger history")
    public Map<String, Object> model() {
        return admin.model();
    }
}
