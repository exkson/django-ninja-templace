from ninja import NinjaAPI

from core.exceptions import (
    AuthenticationException,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


def setup_handlers(app: NinjaAPI):
    @app.exception_handler(AuthenticationException)
    def authentication_exc_handler(request, exc: AuthenticationException):
        return app.create_response(
            request,
            {"detail": exc.message, "code": exc.code},
            status=401,
        )

    @app.exception_handler(ForbiddenError)
    def forbidden_exc_handler(request, exc: ForbiddenError):
        return app.create_response(request, {"detail": exc.message}, status=403)

    @app.exception_handler(NotFoundError)
    def not_found_exc_handler(request, exc: NotFoundError):
        return app.create_response(request, {"detail": exc.message}, status=404)

    @app.exception_handler(ValidationError)
    def validation_exc_handler(request, exc: ValidationError):
        return app.create_response(request, exc.json(), status=400)
