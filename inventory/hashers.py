import hashlib
import hmac

from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LegacyPasswordHasher(BasePasswordHasher):
    algorithm = "legacy_pbkdf2_sha256"

    def encode(self, password, salt, iterations=260000):
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
        return f"{self.algorithm}${iterations}${salt}${digest}"

    def verify(self, password, encoded):
        algorithm, iterations, salt, digest = encoded.split("$", 3)
        return hmac.compare_digest(self.encode(password, salt, int(iterations)), encoded)

    def safe_summary(self, encoded):
        algorithm, iterations, salt, digest = encoded.split("$", 3)
        return {
            "algorithm": algorithm,
            "iterations": iterations,
            "salt": mask_hash(salt),
            "hash": mask_hash(digest),
        }

    def must_update(self, encoded):
        return True
