from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, error_type: str = "app_error"):
        super().__init__(status_code=status_code, detail=detail)
        self.error_type = error_type


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource", id: str = ""):
        detail = f"{resource} not found" if not id else f"{resource} with ID {id} not found"
        super().__init__(status.HTTP_404_NOT_FOUND, detail, "not_found")


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, "conflict")


class ForbiddenError(AppException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, "forbidden")


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, "unauthorized")


class ValidationError(AppException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, "validation_error")


class BadRequestError(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, "bad_request")
