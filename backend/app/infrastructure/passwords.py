from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


class ArgonPasswords:
    def __init__(self) -> None:
        self.hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)
        # Hash ficticio para evitar omitir el coste de verificación de un usuario inexistente.
        self.dummy = self.hasher.hash("unused-random-dummy-password")

    def hash(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        try:
            return self.hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False
