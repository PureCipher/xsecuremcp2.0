"""Administrator-approved registration without issuing applicant sessions."""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from purecipher.auth import RegistryRole
from purecipher.publishers import publisher_id_from_author

REQUEST_ROLES = {"viewer", "publisher", "reviewer"}


def response(data, status=200):
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})


def text(body, key, limit, required=False):
    value = body.get(key, "")
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (required and not value.strip())
    ):
        raise ValueError(
            f"Provide a valid {key.replace('_', ' ')} (maximum {limit} characters)"
        )
    return value.strip()


def mount(registry, prefix):
    store = registry._account_security

    @registry.custom_route(f"{prefix}/register", methods=["POST"])
    async def register(request):
        ip = request.client.host if request.client else "unknown"
        locked, _ = registry._login_lockout.is_locked("workspace-registration", ip)
        if locked:
            return response({"error": "Too many registration attempts; try later"}, 429)
        registry._login_lockout.register_failure("workspace-registration", ip)
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Invalid registration")
            username = text(body, "username", 40, True)
            password = body.get("password")
            if (
                not re.fullmatch(r"[a-z][a-z0-9-]{2,39}", username)
                or not isinstance(password, str)
                or not 12 <= len(password) <= 256
            ):
                raise ValueError(
                    "Use a 3–40 character lowercase username and a password of 12–256 characters"
                )
            role = body.get("requested_role", "viewer")
            if role not in REQUEST_ROLES or body.get("role", role) not in REQUEST_ROLES:
                raise ValueError(
                    "Choose End User, Publisher, or Reviewer; administrator access cannot be requested"
                )
            email = text(body, "email", 254, True)
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("Provide a valid email address")
            registration = {
                "status": "pending",
                "revision": 0,
                "requested_role": role,
                "email": email,
                "email_verified": False,
                "organization": text(
                    body, "organization", 200, role in {"publisher", "reviewer"}
                ),
                "purpose": text(body, "purpose", 1000, True),
                "website": text(body, "website", 500, role == "publisher"),
                "review_experience": text(
                    body, "review_experience", 1000, role == "reviewer"
                ),
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "history": [],
            }
            if registration["website"]:
                url = urlsplit(registration["website"])
                if (
                    url.scheme not in {"http", "https"}
                    or not url.hostname
                    or url.username
                    or url.password
                ):
                    raise ValueError("Provide an http or https organization website")
            if not registry.auth_enabled or registry._bootstrap_required():
                raise ValueError(
                    "An administrator must initialize the registry before registration opens"
                )
            if publisher_id_from_author(username) != username or any(
                publisher_id_from_author(a["username"]) == username
                for a in store.list_accounts()
            ):
                raise ValueError("That username is unavailable")
            created = store.create_account(
                username=username,
                password=password,
                role=RegistryRole.VIEWER,
                source="self-registration",
                display_name=text(body, "display_name", 100, True),
                registration=registration,
            )
            if created is None:
                raise ValueError("That username is unavailable")
            return response(
                {
                    "created": True,
                    "status": "pending",
                    "message": "Your account request is awaiting administrator approval.",
                },
                201,
            )
        except (ValueError, TypeError, AttributeError):
            # Validation errors are safe field-level messages; never echo credentials.
            import sys

            return response(
                {
                    "error": str(sys.exception())
                    if isinstance(sys.exception(), ValueError)
                    else "Invalid registration"
                },
                400,
            )

    @registry.custom_route(f"{prefix}/registration/status", methods=["POST"])
    async def status(request):
        ip = request.client.host if request.client else "unknown"
        key = "account-request-status"
        locked, _ = registry._login_lockout.is_locked(key, ip)
        if locked:
            return response({"error": "Too many attempts; try later"}, 429)
        registry._login_lockout.register_failure(key, ip)
        try:
            body = await request.json()
            username = text(body, "username", 40, True)
            password = body.get("password", "")
            if not isinstance(password, str) or len(password) > 256:
                raise ValueError("Invalid credentials")
            data = store.registration_status(username, password)
            if data is None:
                return response({"error": "Check your username and password"}, 401)
            registry._login_lockout.register_success(key, ip)
            if "reply" in body:
                reply = text(body, "reply", 2000, True)
                store.review_registration(
                    username,
                    status="pending",
                    role=RegistryRole(data["requested_role"]),
                    reason=reply,
                    actor=username,
                    expected_revision=body.get("revision"),
                )
                data = store.registration_status(username, password)
            return response({"request": data})
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            return response(
                {
                    "error": str(exc)
                    if isinstance(exc, ValueError)
                    else "Invalid request"
                },
                400,
            )

    @registry.custom_route(f"{prefix}/admin/account-requests", methods=["GET"])
    async def requests(request):
        session = registry._session_from_request(request)
        if session is None or session.role != RegistryRole.ADMIN:
            return response(
                {"error": "Administrator access required"}, 403 if session else 401
            )
        return response(
            {"requests": [a for a in store.list_accounts() if a.get("registration")]}
        )

    @registry.custom_route(
        f"{prefix}/admin/account-requests/{{username}}", methods=["POST"]
    )
    async def decide(request):
        session = registry._session_from_request(request)
        if session is None or session.role != RegistryRole.ADMIN:
            return response(
                {"error": "Administrator access required"}, 403 if session else 401
            )
        try:
            body = await request.json()
            decision = body.get("decision")
            if decision not in {"approved", "rejected", "information_required"}:
                raise ValueError("Choose approve, reject, or request information")
            user = store.review_registration(
                request.path_params["username"],
                status=decision,
                role=RegistryRole(body.get("role", "viewer")),
                reason=text(body, "reason", 2000),
                actor=session.username,
                expected_revision=body.get("revision"),
            )
            return response({"user": user})
        except (ValueError, TypeError, AttributeError) as exc:
            return response(
                {
                    "error": str(exc)
                    if isinstance(exc, ValueError)
                    else "Invalid decision"
                },
                400,
            )
