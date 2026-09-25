"""Operator accounts: who is using the console, and what they may do.

Before this module the console knew only the operating-system user and a
reviewer name typed into a free-text box. Neither answers the question an
auditor actually asks - *which person analysed this report, and which person
decided it?* - because the first is shared on a plant workstation and the second
is whatever anybody typed.

So every session now begins with a sign-in, and everything the console records
afterwards carries the account that did it.

How the accounts are kept
-------------------------
``users.json`` beside the preferences and the audit trail, one entry per
account. A password is never stored: each account keeps a random 16-byte salt
and the PBKDF2-HMAC-SHA256 digest of the password under it, at the iteration
count OWASP recommends for that function. The iteration count is stored per
account, so it can be raised later without invalidating anyone.

There is no default password. The first time the console starts on a machine
with no accounts, the sign-in page becomes "create the administrator" instead -
a shipped default is the password every installation shares and nobody changes.

Roles
-----
Four, each a strict superset of the one before, because on a plant the
question is always "may this person also do X", never a matrix:

``viewer``    reads everything; changes nothing.
``analyst``   ingests and analyses reports, exports results.
``reviewer``  an HSE expert: decides review cases and trains the model on them.
``admin``     clears records, configures the engines, manages accounts.

What this is not
----------------
A security boundary against someone with access to the files. The accounts
file and the audit trail are on the operator's own disk; anyone who can edit
them can edit them. What the sign-in buys is *attribution* - an honest operator
cannot act under someone else's name by accident, and a dishonest one leaves a
trail whose tampering :meth:`sif.audit.AuditLog.verify` can detect.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, List, Optional

from . import prefs

__all__ = [
    "ROLES", "ROLE_LABELS", "PERMISSIONS", "VIEW", "ANALYSE", "DECIDE", "TRAIN",
    "CLEAR", "CONFIGURE", "MANAGE_USERS", "Account", "Session", "AccountStore",
    "AuthError", "accounts_file_path", "temporary_password",
]

LOGGER = logging.getLogger(__name__)

FILE_NAME = "users.json"

# -- permissions --------------------------------------------------------------

VIEW = "view"
ANALYSE = "analyse"
DECIDE = "decide"
TRAIN = "train"
CLEAR = "clear"
CONFIGURE = "configure"
MANAGE_USERS = "manage users"

ROLES = ("viewer", "analyst", "reviewer", "admin")
ROLE_LABELS: Dict[str, str] = {
    "viewer": "Viewer",
    "analyst": "HSE Analyst",
    "reviewer": "HSE Expert",
    "admin": "Administrator",
}
#: Each role can do everything the one before it can, and more.
PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "viewer": frozenset({VIEW}),
    "analyst": frozenset({VIEW, ANALYSE}),
    "reviewer": frozenset({VIEW, ANALYSE, DECIDE, TRAIN}),
    "admin": frozenset({VIEW, ANALYSE, DECIDE, TRAIN, CLEAR, CONFIGURE, MANAGE_USERS}),
}
#: Plain words for a refusal, so the operator is told what they tried to do.
PERMISSION_WORDS: Dict[str, str] = {
    VIEW: "view the console",
    ANALYSE: "ingest or analyse reports",
    DECIDE: "record a review decision",
    TRAIN: "train the model",
    CLEAR: "clear records",
    CONFIGURE: "change the engine configuration",
    MANAGE_USERS: "manage accounts",
}

# -- policy -------------------------------------------------------------------

#: OWASP's 2023 recommendation for PBKDF2-HMAC-SHA256. Around a third of a
#: second on a workstation: invisible at sign-in, ruinous for a guessing attack.
ITERATIONS = 600_000
SALT_BYTES = 16
MIN_PASSWORD = 8
#: This many wrong passwords in a row locks the account for LOCKOUT_MINUTES.
MAX_FAILURES = 5
LOCKOUT_MINUTES = 5
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def accounts_file_path() -> str:
    """Where the accounts are kept for this operator profile."""
    return os.path.join(prefs.config_directory(), FILE_NAME)


def temporary_password() -> str:
    """A one-time password for an account an administrator creates or resets.

    Twelve characters from a set with no look-alikes (no 0/O, 1/l/I), so it can
    be read aloud or copied from a screen without a transcription mistake.
    """
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _digest(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


class AuthError(Exception):
    """A sign-in or account change was refused. ``str()`` is safe to show."""

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        #: A short machine-readable reason for the audit trail.
        self.reason = reason or "refused"


@dataclass
class Account:
    """One operator. The password itself is never held here."""

    username: str
    full_name: str
    role: str
    salt: str = ""
    password_hash: str = ""
    iterations: int = ITERATIONS
    created_at: str = ""
    created_by: str = ""
    active: bool = True
    #: Set on an account an administrator created or reset: the temporary
    #: password works exactly once, to choose a real one.
    must_change: bool = False
    failed_attempts: int = 0
    locked_until: str = ""
    last_login: str = ""
    #: Optional particulars, shown on the profile and the account list. An
    #: account file written before they existed loads with them blank.
    email: str = ""
    employee_no: str = ""
    site: str = ""
    department: str = ""

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    def to_row(self) -> Dict[str, object]:
        """What the interface may show - no salt, no digest."""
        return {"username": self.username, "full_name": self.full_name,
                "role": self.role, "role_label": self.role_label,
                "active": self.active, "created_at": self.created_at,
                "created_by": self.created_by, "last_login": self.last_login,
                "email": self.email, "employee_no": self.employee_no,
                "site": self.site, "department": self.department,
                "locked": bool(self.locked_until and
                               datetime.fromisoformat(self.locked_until) > _now())}


@dataclass(frozen=True)
class Session:
    """Who is signed in, for the life of one window."""

    username: str
    full_name: str
    role: str
    started_at: str
    #: False for the unattended session tests and scripts run under. The real
    #: entry points never build a window without signing someone in.
    authenticated: bool = True
    session_id: str = field(default_factory=lambda: secrets.token_hex(4))

    @classmethod
    def unattended(cls) -> "Session":
        """A session for code that builds a window without a person at it."""
        try:
            name = getpass.getuser()
        except Exception:  # noqa: BLE001
            name = "local"
        return cls(username=name, full_name=name, role="admin",
                   started_at=_now().isoformat(), authenticated=False)

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def signature(self) -> str:
        """How this person is named on a record: readable, and unique."""
        return f"{self.full_name} ({self.username})"

    def can(self, permission: str) -> bool:
        return permission in PERMISSIONS.get(self.role, frozenset())


class AccountStore:
    """The accounts file: create, authenticate, change."""

    def __init__(self, path: str = "", iterations: int = ITERATIONS) -> None:
        self.path = path or accounts_file_path()
        self.iterations = iterations
        self._lock = threading.Lock()
        self._accounts: Dict[str, Account] = {}
        self.load()

    # -- persistence -------------------------------------------------------

    def load(self) -> "AccountStore":
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            payload = {}
        except Exception as exc:  # noqa: BLE001
            # An unreadable accounts file must not silently become "no accounts"
            # - that would offer to create a fresh administrator over it.
            raise AuthError(f"The accounts file could not be read: {exc}",
                            "accounts unreadable") from exc
        known = set(Account.__dataclass_fields__)
        self._accounts = {
            str(item["username"]): Account(**{k: v for k, v in item.items() if k in known})
            for item in payload.get("accounts", []) if item.get("username")
        }
        return self

    def save(self) -> None:
        """Write atomically: a crash mid-write must not lose every account."""
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        temporary = f"{self.path}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump({"version": 1,
                       "accounts": [asdict(item) for item in self._accounts.values()]},
                      handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    # -- reading -----------------------------------------------------------

    def has_accounts(self) -> bool:
        return bool(self._accounts)

    def get(self, username: str) -> Optional[Account]:
        return self._accounts.get(username.strip().lower())

    def resolve(self, name: str) -> str:
        """The username for a username or an email address; ``name`` if neither."""
        name = name.strip().lower()
        if name in self._accounts or "@" not in name:
            return name
        return next((account.username for account in self._accounts.values()
                     if account.email and account.email.lower() == name), name)

    PROFILE_FIELDS = ("email", "employee_no", "site", "department")

    def set_profile(self, username: str, **values: str) -> Account:
        """Set an account's particulars: email, employee number, site, department."""
        account = self._require(username)
        email = values.get("email")
        if email is not None:
            email = email.strip().lower()
            if email and not EMAIL.match(email):
                raise AuthError("That does not look like an email address.", "bad email")
            if email and any(other.email.lower() == email and other.username != account.username
                             for other in self._accounts.values()):
                raise AuthError("Another account already uses that email.", "duplicate email")
        with self._lock:
            for name in self.PROFILE_FIELDS:
                if name in values and values[name] is not None:
                    value = email if name == "email" else " ".join(str(values[name]).split())
                    setattr(account, name, value)
            self.save()
        return account

    def accounts(self) -> List[Account]:
        return sorted(self._accounts.values(), key=lambda item: item.username)

    def administrators(self) -> List[Account]:
        return [item for item in self._accounts.values()
                if item.role == "admin" and item.active]

    # -- changing ----------------------------------------------------------

    def create(self, username: str, full_name: str, role: str, password: str,
               created_by: str = "", must_change: bool = False) -> Account:
        username = username.strip().lower()
        full_name = " ".join(full_name.split())
        if not USERNAME.match(username):
            raise AuthError("A username is 3-32 characters: lower-case letters, "
                            "digits, dot, dash or underscore.", "bad username")
        if not full_name:
            raise AuthError("Give the person's full name - it is what appears on "
                            "every record they make.", "no name")
        if role not in ROLES:
            raise AuthError(f"Unknown role {role!r}.", "bad role")
        self._check_password(password, username)
        with self._lock:
            if username in self._accounts:
                raise AuthError(f"There is already an account called {username}.",
                                "duplicate")
            account = Account(username=username, full_name=full_name, role=role,
                              iterations=self.iterations,
                              created_at=_now().isoformat(), created_by=created_by,
                              must_change=must_change)
            self._set_secret(account, password)
            self._accounts[username] = account
            self.save()
        LOGGER.info("Account %s created (%s) by %s", username, role, created_by or "setup")
        return account

    def authenticate(self, username: str, password: str) -> Session:
        """Sign someone in, or raise :class:`AuthError` saying why not.

        ``username`` may also be the account's email address.
        """
        username = self.resolve(username)
        with self._lock:
            account = self._accounts.get(username)
            if account is None:
                # Spend the same time as a real check, so how long a refusal
                # takes does not say whether the username exists.
                _digest(password, b"\0" * SALT_BYTES, self.iterations)
                raise AuthError("The username or password is not right.", "unknown user")
            if not account.active:
                raise AuthError("This account has been disabled. Ask an administrator.",
                                "disabled")
            if account.locked_until:
                until = datetime.fromisoformat(account.locked_until)
                if until > _now():
                    minutes = max(1, int((until - _now()).total_seconds() // 60) + 1)
                    raise AuthError(f"Too many wrong passwords. Try again in "
                                    f"{minutes} minute(s).", "locked")
                account.locked_until = ""
                account.failed_attempts = 0
            if not self._matches(account, password):
                account.failed_attempts += 1
                reason = "wrong password"
                if account.failed_attempts >= MAX_FAILURES:
                    account.locked_until = (_now() + timedelta(minutes=LOCKOUT_MINUTES)
                                            ).isoformat()
                    reason = "locked out"
                self.save()
                raise AuthError("The username or password is not right.", reason)
            account.failed_attempts = 0
            account.locked_until = ""
            account.last_login = _now().isoformat()
            self.save()
        return Session(username=account.username, full_name=account.full_name,
                       role=account.role, started_at=account.last_login)

    def change_password(self, username: str, current: str, new: str) -> None:
        """The owner choosing a new password - which needs the current one."""
        account = self.get(username)
        if account is None or not self._matches(account, current):
            raise AuthError("The current password is not right.", "wrong password")
        if hmac.compare_digest(current, new):
            raise AuthError("Choose a password different from the current one.",
                            "unchanged")
        self._check_password(new, account.username)
        with self._lock:
            self._set_secret(account, new)
            account.must_change = False
            self.save()

    def reset_password(self, username: str, by: str) -> str:
        """An administrator issuing a one-time password; returns it once."""
        account = self._require(username)
        password = temporary_password()
        with self._lock:
            self._set_secret(account, password)
            account.must_change = True
            account.failed_attempts = 0
            account.locked_until = ""
            self.save()
        LOGGER.info("Password for %s reset by %s", account.username, by)
        return password

    def set_role(self, username: str, role: str) -> None:
        if role not in ROLES:
            raise AuthError(f"Unknown role {role!r}.", "bad role")
        account = self._require(username)
        if account.role == "admin" and role != "admin":
            self._keep_an_administrator(account)
        with self._lock:
            account.role = role
            self.save()

    def set_active(self, username: str, active: bool) -> None:
        account = self._require(username)
        if not active and account.role == "admin":
            self._keep_an_administrator(account)
        with self._lock:
            account.active = active
            self.save()

    # -- internals ---------------------------------------------------------

    def _require(self, username: str) -> Account:
        account = self.get(username)
        if account is None:
            raise AuthError(f"There is no account called {username}.", "unknown user")
        return account

    def _keep_an_administrator(self, account: Account) -> None:
        """Refuse the change that would leave nobody able to manage accounts."""
        others = [item for item in self.administrators() if item is not account]
        if not others:
            raise AuthError("This is the last active administrator. Make someone "
                            "else an administrator first.", "last admin")

    @staticmethod
    def _check_password(password: str, username: str) -> None:
        if len(password) < MIN_PASSWORD:
            raise AuthError(f"A password needs at least {MIN_PASSWORD} characters.",
                            "short password")
        if password.strip().lower() == username:
            raise AuthError("A password cannot be the username.", "password is username")

    def _set_secret(self, account: Account, password: str) -> None:
        salt = secrets.token_bytes(SALT_BYTES)
        account.salt = salt.hex()
        account.iterations = self.iterations
        account.password_hash = _digest(password, salt, account.iterations).hex()

    @staticmethod
    def _matches(account: Account, password: str) -> bool:
        if not account.salt or not account.password_hash:
            return False
        candidate = _digest(password, bytes.fromhex(account.salt), account.iterations)
        return hmac.compare_digest(candidate.hex(), account.password_hash)
