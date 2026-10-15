"""Domain exceptions. Keep free of package imports (imported by config.py)."""


class MediVaultError(Exception):
    code = "internal_error"
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ConfigError(MediVaultError):
    code = "config_error"
    status_code = 500


class NotFoundError(MediVaultError):
    code = "not_found"
    status_code = 404


class ConflictError(MediVaultError):
    code = "conflict"
    status_code = 409


class ValidationFailure(MediVaultError):
    code = "validation_error"
    status_code = 422


class IngestError(MediVaultError):
    code = "ingest_failed"
    status_code = 422


class RetrievalError(MediVaultError):
    code = "retrieval_failed"
    status_code = 500


class AgentError(MediVaultError):
    code = "agent_failed"
    status_code = 500
