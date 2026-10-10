"""Runtime errors mapped to the public API at the transport boundary."""


class RuntimeProblem(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status
        super().__init__(code)
