"""HTTP handshake and emergency deny control for the console Entra boundary."""
from urllib.parse import urlencode, urlsplit

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.console_entra_v1 import FLOW_COOKIE, SESSION_SECONDS, MicrosoftLogin
from src.operations_console_v1 import ConsoleError


SESSION_COOKIE = "console_session"


def install_entra_routes(app, console, identity, *, render_page):
    provider = MicrosoftLogin(identity.config)
    app.state.microsoft_login = provider

    def failure(status=403):
        response = HTMLResponse(render_page(
            '<section class="room login-card"><h1>Aanmelden niet gelukt</h1>'
            '<p>Controleer of je werkaccount toegang heeft tot Metis. Neem anders contact op met je Metis-beheerder.</p>'
            '<p>Bij een tijdelijke storing kun je het opnieuw proberen.</p>'
            '<a href="/login">Terug naar aanmelden</a></section>'
        ), status_code=status, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.delete_cookie(FLOW_COOKIE, secure=True, httponly=True, samesite="lax")
        response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax")
        return response

    @app.middleware("http")
    async def renew_on_navigation(request: Request, call_next):
        public = request.url.path in {"/", "/login", "/health", "/auth/microsoft", "/auth/microsoft/callback"} or request.url.path.startswith("/brand/")
        if request.method == "GET" and not public:
            from starlette.concurrency import run_in_threadpool
            try:
                await run_in_threadpool(identity.session_account, request.cookies.get(SESSION_COOKIE))
            except ConsoleError as exc:
                if exc.code == "workflow_identity_unavailable":
                    return failure(503)
                return RedirectResponse("/auth/microsoft?" + urlencode({"next": request.url.path + ("?" + request.url.query if request.url.query else "")}), status_code=303)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/auth/microsoft")
    def begin(request: Request):
        try:
            # Replacing an abandoned handshake consumes its record, if any.
            if request.cookies.get(FLOW_COOKIE):
                try:
                    identity.consume_flow(request.cookies[FLOW_COOKIE])
                except ConsoleError:
                    pass
            flow = app.state.microsoft_login.begin()
            target = request.query_params.get("next", "/")
            parsed = urlsplit(target)
            if (not target.startswith("/") or target.startswith("//") or "\\" in target
                    or parsed.netloc or parsed.scheme or any(ord(c) < 32 for c in target)
                    or parsed.path.startswith("/auth/") or parsed.path == "/logout"):
                target = "/"
            flow["metis_return_to"] = target
            handle = identity.save_flow(flow)
            response = RedirectResponse(flow["auth_uri"], status_code=303)
            response.set_cookie(FLOW_COOKIE, handle, max_age=600, secure=True, httponly=True, samesite="lax", path="/")
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        except Exception:
            return failure(503)

    @app.get("/auth/microsoft/callback")
    def callback(request: Request):
        try:
            flow = identity.consume_flow(request.cookies.get(FLOW_COOKIE))
            supplied = dict(request.query_params)
            # Fail before network exchange for missing/duplicate/mismatched state.
            if (len(request.query_params.getlist("state")) != 1
                    or not supplied.get("state") or supplied["state"] != flow.get("state")):
                return failure()
            claims = app.state.microsoft_login.finish(flow, supplied)
            session = identity.sign_in(claims)
            # Session rotation: a successful sign-in invalidates this browser's previous session.
            console.logout(request.cookies.get(SESSION_COOKIE))
            response = RedirectResponse(flow.get("metis_return_to", "/"), status_code=303)
            response.set_cookie(SESSION_COOKIE, session["token"], max_age=SESSION_SECONDS, secure=True, httponly=True, samesite="lax")
            response.delete_cookie(FLOW_COOKIE, secure=True, httponly=True, samesite="lax")
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        except (ConsoleError, ValueError):
            return failure()
        except Exception:
            return failure(503)

    @app.post("/accounts/access")
    def access(request: Request, account_id: str = Form(...), blocked: str = Form(...)):
        if blocked not in {"true", "false"}:
            raise ConsoleError("entra_access_denied")
        identity.set_blocked(actor_token=request.cookies.get(SESSION_COOKIE, ""), account_id=account_id, blocked=blocked == "true")
        return RedirectResponse("/accounts", status_code=303)
