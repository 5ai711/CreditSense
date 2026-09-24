package com.creditsense.security;

import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

/**
 * The refresh token travels only in this cookie: HttpOnly so page scripts cannot read it, SameSite=Strict so
 * other sites cannot make the browser send it, and scoped to the auth endpoints so no other request carries it.
 */
@Component
public class RefreshCookie {

    public static final String NAME = "cs_refresh";
    static final String PATH = "/api/auth";

    private final RefreshCookieProperties props;
    private final JwtProperties jwt;

    public RefreshCookie(RefreshCookieProperties props, JwtProperties jwt) {
        this.props = props;
        this.jwt = jwt;
    }

    public String issue(String refreshToken) {
        return base(refreshToken).maxAge(jwt.refreshTokenTtl()).build().toString();
    }

    public String clear() {
        return base("").maxAge(0).build().toString();
    }

    private ResponseCookie.ResponseCookieBuilder base(String value) {
        return ResponseCookie.from(NAME, value).httpOnly(true).secure(props.secure()).sameSite("Strict").path(PATH);
    }
}
