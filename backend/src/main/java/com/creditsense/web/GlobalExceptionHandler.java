package com.creditsense.web;

import com.creditsense.common.ApiException;
import com.creditsense.common.RateLimitedException;
import com.creditsense.risk.MlUnavailableException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authorization.AuthorizationDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/** One error shape for every failure: {timestamp, status, error, message, path, fieldErrors?}. */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    public record FieldError(String field, String message) {}

    @ExceptionHandler(ApiException.class)
    ResponseEntity<Map<String, Object>> api(ApiException e, HttpServletRequest req) {
        ResponseEntity<Map<String, Object>> res = body(e.status(), e.getMessage(), req, null);
        if (e instanceof RateLimitedException limited) {
            return ResponseEntity.status(res.getStatusCode())
                    .header(HttpHeaders.RETRY_AFTER, Long.toString(limited.retryAfterSeconds()))
                    .body(res.getBody());
        }
        return res;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<Map<String, Object>> invalid(MethodArgumentNotValidException e, HttpServletRequest req) {
        List<FieldError> fields = e.getBindingResult().getFieldErrors().stream()
                .map(f -> new FieldError(f.getField(), f.getDefaultMessage())).toList();
        return body(HttpStatus.BAD_REQUEST, "request validation failed", req, fields);
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    ResponseEntity<Map<String, Object>> invalidParams(HandlerMethodValidationException e, HttpServletRequest req) {
        List<FieldError> fields = e.getParameterValidationResults().stream()
                .flatMap(r -> r.getResolvableErrors().stream()
                        .map(err -> new FieldError(r.getMethodParameter().getParameterName(), err.getDefaultMessage())))
                .toList();
        return body(HttpStatus.BAD_REQUEST, "request validation failed", req, fields);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    ResponseEntity<Map<String, Object>> constraint(ConstraintViolationException e, HttpServletRequest req) {
        List<FieldError> fields = e.getConstraintViolations().stream()
                .map(v -> new FieldError(v.getPropertyPath().toString(), v.getMessage())).toList();
        return body(HttpStatus.BAD_REQUEST, "request validation failed", req, fields);
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class})
    ResponseEntity<Map<String, Object>> unreadable(Exception e, HttpServletRequest req) {
        return body(HttpStatus.BAD_REQUEST, "malformed request: " + rootMessage(e), req, null);
    }

    @ExceptionHandler({AccessDeniedException.class, AuthorizationDeniedException.class})
    ResponseEntity<Map<String, Object>> denied(Exception e, HttpServletRequest req) {
        return body(HttpStatus.FORBIDDEN, "you do not have access to this resource", req, null);
    }

    @ExceptionHandler(MlUnavailableException.class)
    ResponseEntity<Map<String, Object>> mlDown(MlUnavailableException e, HttpServletRequest req) {
        return body(HttpStatus.SERVICE_UNAVAILABLE, e.getMessage(), req, null);
    }

    @ExceptionHandler(ObjectOptimisticLockingFailureException.class)
    ResponseEntity<Map<String, Object>> stale(Exception e, HttpServletRequest req) {
        return body(HttpStatus.CONFLICT, "the application was changed by someone else; reload and retry", req, null);
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<Map<String, Object>> noResource(NoResourceFoundException e, HttpServletRequest req) {
        return body(HttpStatus.NOT_FOUND, "no such endpoint", req, null);
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<Map<String, Object>> unexpected(Exception e, HttpServletRequest req) {
        log.error("unhandled error on {} {}", req.getMethod(), req.getRequestURI(), e);
        return body(HttpStatus.INTERNAL_SERVER_ERROR, "unexpected error", req, null);
    }

    private static String rootMessage(Throwable e) {
        Throwable t = e;
        while (t.getCause() != null && t.getCause() != t) t = t.getCause();
        String m = t.getMessage();
        return m == null ? t.getClass().getSimpleName() : m.length() > 200 ? m.substring(0, 200) : m;
    }

    private static ResponseEntity<Map<String, Object>> body(HttpStatus status, String message, HttpServletRequest req,
            List<FieldError> fields) {
        Map<String, Object> b = new LinkedHashMap<>();
        b.put("timestamp", Instant.now().toString());
        b.put("status", status.value());
        b.put("error", status.getReasonPhrase());
        b.put("message", message);
        b.put("path", req.getRequestURI());
        if (fields != null) b.put("fieldErrors", fields);
        return ResponseEntity.status(status).body(b);
    }
}
