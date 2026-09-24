package com.creditsense.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "kyc_documents")
@Getter
@Setter
public class KycDocument {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "application_id")
    private LoanApplication application;

    @Enumerated(EnumType.STRING)
    @Column(name = "doc_type", nullable = false)
    private DocumentType docType;

    @Column(name = "document_number", nullable = false)
    private String documentNumber;

    /** For bank statements: how many months the statement covers. */
    @Column(name = "months_covered")
    private Integer monthsCovered;

    @Column(nullable = false)
    private boolean verified;

    @Column(name = "verification_note")
    private String verificationNote;
}
