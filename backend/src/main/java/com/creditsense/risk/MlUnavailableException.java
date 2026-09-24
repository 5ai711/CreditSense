package com.creditsense.risk;

/** The ML service could not be reached or did not answer usefully, after retries. */
public class MlUnavailableException extends RuntimeException {
    public MlUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
