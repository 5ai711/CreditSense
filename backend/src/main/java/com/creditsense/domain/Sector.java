package com.creditsense.domain;

/** Business sectors, with the label the ML service expects. */
public enum Sector {
    MANUFACTURING("Manufacturing"),
    TRADING("Trading"),
    SERVICES("Services"),
    RETAIL("Retail"),
    AGRI_ALLIED("Agri-allied"),
    HOSPITALITY("Hospitality");

    private final String modelLabel;

    Sector(String modelLabel) {
        this.modelLabel = modelLabel;
    }

    public String modelLabel() {
        return modelLabel;
    }
}
