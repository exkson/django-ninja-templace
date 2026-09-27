# Handling API errors (frontend guide)

The backend uses a small set of exception classes, each mapped to a fixed HTTP status and JSON body. A client only needs to branch on the **status code** — the body shape per status is stable across endpoints.

Per-endpoint response maps in the OpenAPI schema list the statuses each route may return. This document describes what the body looks like for each one and how to react.

## 400 — Validation error

The submitted payload was rejected (missing/invalid field, failed business rule, cross-field invariant, guard on existing state).

**Body:** flat `{ field: [messages] }` map.

```json
{
  "first_name": ["cannot be empty"],
  "birthdate": ["must be at least 18 years old"]
}
```

Keys are the names of the offending fields, exactly as sent in the request. Values are arrays of human-readable, already-translated error messages.

The reserved key `"detail"` is used when the error is **not tied to a specific field** but applies to the whole request — e.g. a guard like "this account is already active":

```json
{ "detail": ["Account is already active."] }
```

**Client should:**

- Iterate the map. For each key matching a form field, render the list of messages under that field. For the `"detail"` key, render at the top of the form (or as a toast).
- Treat the messages as display-ready — no extra translation needed (the server has already applied i18n).
- Do **not** retry automatically. The user must correct input.

```ts
type ValidationErrorBody = Record<string, string[]>;

function applyValidationErrors(body: ValidationErrorBody, form: FormApi) {
  for (const [key, messages] of Object.entries(body)) {
    if (key === "detail") form.setFormError(messages.join(" "));
    else form.setFieldError(key, messages.join(" "));
  }
}
```

## 401 — Authentication error

The request is missing a token, or the token is invalid/expired.

**Body:**

```json
{ "detail": "...", "code": "invalid-credentials" }
```

`code` is a stable machine-readable enum — branch on this rather than parsing `detail`:

| `code`                   | Meaning                                | Client action                                                  |
| ------------------------ | -------------------------------------- | -------------------------------------------------------------- |
| `invalid-credentials`    | Login failed (wrong email/phone/OTP)   | Show error on login form; let user retry.                      |
| `invalid-token`          | Access token is malformed or unknown   | Clear stored tokens, redirect to login.                        |
| `invalid-refresh-token`  | Refresh token is malformed or unknown  | Clear stored tokens, redirect to login.                        |
| `refresh-token-expired`  | Refresh token expired                  | Clear stored tokens, redirect to login.                        |
| `banned-account`         | Account was banned by staff            | Clear stored tokens, show a "account suspended" screen.       |

**Client should:**

- For `invalid-credentials`, surface `detail` near the credential field that was being submitted.
- For the token codes and `banned-account`, log the user out locally and route to the login screen. Do not loop on the failing request.
- Access-token expiry on a normal request should be handled by your refresh flow before reaching UI code; only surface 401 to the user when refresh itself fails.

## 403 — Forbidden

The user is authenticated but is not allowed to perform this action (insufficient permission, state-based guard, banned account, etc.).

**Body:**

```json
{ "detail": "..." }
```

`detail` is a single human-readable, translated string.

**Client should:**

- Render `detail` as the error message — it is already user-facing.
- Do **not** retry. 403 is a hard "no" for the current user/state.
- Do **not** clear tokens — the session is still valid; only this action is denied.

## 404 — Not found

The resource does not exist **or** the caller is not allowed to know it exists — the two cases are deliberately indistinguishable.

**Body:**

```json
{ "detail": "Resource not found." }
```

**Client should:** show a "not found" state; don't retry.

## 422 — Request could not be parsed

Returned by django-ninja **before** the request reaches our handler, when the request itself fails to parse against the endpoint's declared schema — missing required field, wrong type, malformed JSON, missing query/path/form parameter, etc. This is distinct from 400, which is raised by our domain code after the request has been parsed successfully.

**Body:** django-ninja's default Pydantic-style error list.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "payload", "first_name"],
      "msg": "Field required"
    },
    {
      "type": "string_type",
      "loc": ["body", "payload", "birthdate"],
      "msg": "Input should be a valid string"
    }
  ]
}
```

Each entry has:

- `loc` — path to the offending input. The first element is the source (`"body"`, `"query"`, `"path"`, `"form"`); the last element is usually the field name.
- `msg` — English-only, **not translated**. Treat as developer-facing.
- `type` — Pydantic error code (`"missing"`, `"string_type"`, `"int_parsing"`, …) — useful for branching, not for display.

**Client should:**

- Treat 422 as a **client bug**, not a user-input problem: if the form is well-formed in the UI, the user should never see a raw 422. Validate required fields and types client-side before submitting.
- If 422 still occurs in the wild, log it to error tracking with the full `detail` payload — it indicates a contract drift between client and server.
- As a fallback UX, derive the field from `loc[loc.length - 1]` and show a generic "this field is invalid" message; do not surface `msg` directly (it's not translated and not user-friendly).

```ts
type Ninja422Body = {
  detail: Array<{ type: string; loc: (string | number)[]; msg: string }>;
};

function fieldFromLoc(loc: (string | number)[]): string | null {
  const last = loc[loc.length - 1];
  return typeof last === "string" ? last : null;
}
```

## 5xx — Server error

Unhandled server-side failures. Body shape is **not guaranteed** — django-ninja may return a default error body or a stack trace in dev.

**Client should:**

- Show a generic "something went wrong, please try again" message.
- Optionally retry idempotent requests once with backoff.
- Report to error tracking (Sentry, etc.) — these are bugs, not expected responses.

## Quick reference

| Status | Body shape                                                         | Source                          |
| ------ | ------------------------------------------------------------------ | ------------------------------- |
| 400    | `Record<string, string[]>` (flat)                                  | `ValidationError` (domain)      |
| 401    | `{ detail: string, code: AuthExceptionCode }`                      | `AuthenticationException`       |
| 403    | `{ detail: string }`                                               | `ForbiddenError`                |
| 404    | `{ detail: string }`                                               | `NotFoundError`                 |
| 422    | `{ detail: [{ type, loc, msg }, ...] }`                            | django-ninja request parsing    |
| 5xx    | unspecified                                                        | unhandled                       |

A single shared error-handling layer in the client (interceptor / fetch wrapper) can branch on status and dispatch to the appropriate UI handler — individual call sites only need to handle 400 (form errors) and the success body.
