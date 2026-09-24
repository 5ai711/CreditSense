package com.creditsense.domain;

public enum CheckType {
    GST_VALIDITY(Category.GST),
    KYC_COMPLETENESS(Category.KYC),
    DUPLICATE_PAN(Category.FRAUD),
    ADDRESS_MISMATCH(Category.FRAUD),
    BLACKLIST(Category.FRAUD),
    VELOCITY(Category.FRAUD);

    public enum Category { GST, KYC, FRAUD }

    private final Category category;

    CheckType(Category category) {
        this.category = category;
    }

    public Category category() {
        return category;
    }
}
