package com.creditsense.web;

import com.creditsense.auth.AuthDtos.*;
import com.creditsense.auth.AuthService;
import com.creditsense.common.ApiException;
import com.creditsense.security.AuthUser;
import com.creditsense.security.RefreshCookie;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

/**
 * Sessions: the response body carries a short-lived access token; the refresh token is set as an HttpOnly
 * cookie and is never readable by page scripts. API clients without cookies may still send it in the body.
 */
@RestController
@RequestMapping("/api/auth")
@Tag(name = "Authentication")
public class AuthController {

    private final AuthService auth;
    private final RefreshCookie cookie;

    public AuthController(AuthService auth, RefreshCookie cookie) {
        this.auth = auth;
        this.cookie = cookie;
    }

    @PostMapping("/register")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Register an applicant account and sign in")
    public SessionResponse register(@Valid @RequestBody RegisterRequest req, HttpServletResponse res) {
        return start(auth.register(req), res);
    }

    @PostMapping("/login")
    @Operation(summary = "Exchange credentials for an access token; the refresh token is set as an HttpOnly cookie")
    public SessionResponse login(@Valid @RequestBody LoginRequest req, HttpServletRequest http, HttpServletResponse res) {
        return start(auth.login(req, http.getRemoteAddr()), res);
    }

    @PostMapping("/refresh")
    @Operation(summary = "Rotate the refresh token (cookie, or body for API clients) and get a new access token")
    public SessionResponse refresh(@CookieValue(name = RefreshCookie.NAME, required = false) String fromCookie,
            @RequestBody(required = false) RefreshRequest body, HttpServletResponse res) {
        try {
            return start(auth.refresh(presented(fromCookie, body)), res);
        } catch (ApiException e) {
            res.addHeader(HttpHeaders.SET_COOKIE, cookie.clear()); // a dead token is not worth sending again
            throw e;
        }
    }

    @PostMapping("/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Revoke the refresh token and clear the cookie")
    public void logout(@CookieValue(name = RefreshCookie.NAME, required = false) String fromCookie,
            @RequestBody(required = false) RefreshRequest body, HttpServletResponse res) {
        auth.logout(presented(fromCookie, body));
        res.addHeader(HttpHeaders.SET_COOKIE, cookie.clear());
    }

    @GetMapping("/me")
    public UserDto me(@AuthenticationPrincipal AuthUser user) {
        return auth.me(user.id());
    }

    private SessionResponse start(TokenResponse tokens, HttpServletResponse res) {
        res.addHeader(HttpHeaders.SET_COOKIE, cookie.issue(tokens.refreshToken()));
        return tokens.session();
    }

    private static String presented(String fromCookie, RefreshRequest body) {
        if (fromCookie != null && !fromCookie.isBlank()) return fromCookie;
        return body == null ? null : body.refreshToken();
    }
}
