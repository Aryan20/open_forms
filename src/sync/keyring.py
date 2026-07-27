# keyring.py
#
# Copyright 2025 Aryan Kaushik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Credential storage via the desktop Secret portal, encrypted with AES-256-GCM
using ctypes/libcrypto.
"""

import base64
import ctypes
import ctypes.util
import hashlib
import json
import os
import select
import threading
import time

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


def _load_libcrypto():
    candidates = ["libcrypto.so.3", "libcrypto.so.1.1", "libcrypto.so"]
    found = ctypes.util.find_library("crypto")
    if found:
        candidates.append(found)
    for name in candidates:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


_libcrypto = _load_libcrypto()
_HAS_CRYPTO = _libcrypto is not None

if _HAS_CRYPTO:
    _libcrypto.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
    _libcrypto.EVP_CIPHER_CTX_new.argtypes = []
    _libcrypto.EVP_CIPHER_CTX_free.restype = None
    _libcrypto.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
    _libcrypto.EVP_aes_256_gcm.restype = ctypes.c_void_p
    _libcrypto.EVP_aes_256_gcm.argtypes = []
    _libcrypto.EVP_EncryptInit_ex.restype = ctypes.c_int
    _libcrypto.EVP_EncryptInit_ex.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
    ]
    _libcrypto.EVP_DecryptInit_ex.restype = ctypes.c_int
    _libcrypto.EVP_DecryptInit_ex.argtypes = _libcrypto.EVP_EncryptInit_ex.argtypes
    _libcrypto.EVP_EncryptUpdate.restype = ctypes.c_int
    _libcrypto.EVP_EncryptUpdate.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int), ctypes.c_char_p, ctypes.c_int,
    ]
    _libcrypto.EVP_DecryptUpdate.restype = ctypes.c_int
    _libcrypto.EVP_DecryptUpdate.argtypes = _libcrypto.EVP_EncryptUpdate.argtypes
    _libcrypto.EVP_EncryptFinal_ex.restype = ctypes.c_int
    _libcrypto.EVP_EncryptFinal_ex.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    _libcrypto.EVP_DecryptFinal_ex.restype = ctypes.c_int
    _libcrypto.EVP_DecryptFinal_ex.argtypes = _libcrypto.EVP_EncryptFinal_ex.argtypes
    _libcrypto.EVP_CIPHER_CTX_ctrl.restype = ctypes.c_int
    _libcrypto.EVP_CIPHER_CTX_ctrl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]

_EVP_CTRL_GCM_SET_IVLEN = 0x9
_EVP_CTRL_GCM_GET_TAG = 0x10
_EVP_CTRL_GCM_SET_TAG = 0x11
_GCM_TAG_LEN = 16


class _OpenSSLError(Exception):
    """Raised on an OpenSSL EVP call failure, including AES-GCM tag verification failure."""


def _aes256gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """AES-256-GCM encrypt via libcrypto; returns ciphertext with the 16-byte tag appended."""
    assert _libcrypto is not None  # callers must check _HAS_CRYPTO/_require_crypto() first
    ctx = _libcrypto.EVP_CIPHER_CTX_new()
    if not ctx:
        raise _OpenSSLError("EVP_CIPHER_CTX_new failed")
    try:
        if _libcrypto.EVP_EncryptInit_ex(ctx, _libcrypto.EVP_aes_256_gcm(), None, None, None) != 1:
            raise _OpenSSLError("cipher init failed")
        if _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_GCM_SET_IVLEN, len(nonce), None) != 1:
            raise _OpenSSLError("set IV length failed")
        if _libcrypto.EVP_EncryptInit_ex(ctx, None, None, key, nonce) != 1:
            raise _OpenSSLError("key/IV init failed")

        outlen = ctypes.c_int(0)
        buf = ctypes.create_string_buffer(len(plaintext) + 16)
        if _libcrypto.EVP_EncryptUpdate(ctx, buf, ctypes.byref(outlen), plaintext, len(plaintext)) != 1:
            raise _OpenSSLError("encrypt update failed")
        written = outlen.value

        final_len = ctypes.c_int(0)
        final_buf = ctypes.create_string_buffer(16)
        if _libcrypto.EVP_EncryptFinal_ex(ctx, final_buf, ctypes.byref(final_len)) != 1:
            raise _OpenSSLError("encrypt final failed")

        tag = ctypes.create_string_buffer(_GCM_TAG_LEN)
        if _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_GCM_GET_TAG, _GCM_TAG_LEN, tag) != 1:
            raise _OpenSSLError("get tag failed")

        return buf.raw[:written] + final_buf.raw[:final_len.value] + tag.raw
    finally:
        _libcrypto.EVP_CIPHER_CTX_free(ctx)


def _aes256gcm_decrypt(key: bytes, nonce: bytes, ciphertext_and_tag: bytes) -> bytes:
    assert _libcrypto is not None  # callers must check _HAS_CRYPTO/_require_crypto() first
    if len(ciphertext_and_tag) < _GCM_TAG_LEN:
        raise _OpenSSLError("ciphertext too short")
    ciphertext, tag = ciphertext_and_tag[:-_GCM_TAG_LEN], ciphertext_and_tag[-_GCM_TAG_LEN:]

    ctx = _libcrypto.EVP_CIPHER_CTX_new()
    if not ctx:
        raise _OpenSSLError("EVP_CIPHER_CTX_new failed")
    try:
        if _libcrypto.EVP_DecryptInit_ex(ctx, _libcrypto.EVP_aes_256_gcm(), None, None, None) != 1:
            raise _OpenSSLError("cipher init failed")
        if _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_GCM_SET_IVLEN, len(nonce), None) != 1:
            raise _OpenSSLError("set IV length failed")
        if _libcrypto.EVP_DecryptInit_ex(ctx, None, None, key, nonce) != 1:
            raise _OpenSSLError("key/IV init failed")

        outlen = ctypes.c_int(0)
        buf = ctypes.create_string_buffer(len(ciphertext) + 16)
        if _libcrypto.EVP_DecryptUpdate(ctx, buf, ctypes.byref(outlen), ciphertext, len(ciphertext)) != 1:
            raise _OpenSSLError("decrypt update failed")
        written = outlen.value

        if _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_GCM_SET_TAG, _GCM_TAG_LEN, tag) != 1:
            raise _OpenSSLError("set tag failed")

        final_len = ctypes.c_int(0)
        final_buf = ctypes.create_string_buffer(16)
        if _libcrypto.EVP_DecryptFinal_ex(ctx, final_buf, ctypes.byref(final_len)) != 1:
            raise _OpenSSLError("tag verification failed - wrong key or corrupted data")

        return buf.raw[:written] + final_buf.raw[:final_len.value]
    finally:
        _libcrypto.EVP_CIPHER_CTX_free(ctx)


_PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
_PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_SECRET_IFACE = "org.freedesktop.portal.Secret"
_READ_GRACE_SEC = 0.2

_APP_ID = "in.aryank.openforms"

# Cached for the process lifetime, including failures, so repeated calls
# don't each re-block on a fresh portal round trip.
_cached_key: bytes | None = None
_key_unavailable = False

# Guards the read-modify-write of the secrets file - store/clear from the
# sync worker thread and the settings dialog on the main thread can race.
_file_lock = threading.Lock()


class KeyringUnavailable(Exception):
    """Raised when the Secret portal (or the crypto backend) is unavailable."""


def _secrets_path() -> str:
    config_dir = os.path.join(GLib.get_user_config_dir(), _APP_ID)
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "secrets.enc.json")


def _read_with_deadline(fd: int, timeout_sec: float) -> bytes:
    """Read the portal's reply, bounded by timeout_sec; always closes fd. Doesn't
    wait for EOF - a Gio.UnixFDList dup can keep the pipe's write end open forever."""
    deadline = time.monotonic() + timeout_sec
    remaining = deadline - time.monotonic()
    try:
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise KeyringUnavailable("Timed out reading the secret from the portal")
        chunks = [os.read(fd, 4096)]
        if not chunks[0]:
            return b""
        while select.select([fd], [], [], _READ_GRACE_SEC)[0]:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _retrieve_portal_secret(timeout_sec: int = 5) -> bytes:
    """Call org.freedesktop.portal.Secret.RetrieveSecret and read the raw
    key bytes the portal writes back through a pipe, bounded by timeout_sec."""
    read_fd = write_fd = -1
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        read_fd, write_fd = os.pipe()
        fd_list = Gio.UnixFDList.new()
        handle = fd_list.append(write_fd)
        params = GLib.Variant("(ha{sv})", (handle, {}))

        bus.call_with_unix_fd_list_sync(
            _PORTAL_BUS_NAME, _PORTAL_OBJECT_PATH, _PORTAL_SECRET_IFACE,
            "RetrieveSecret", params, GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE, int(timeout_sec * 1000), fd_list, None,
        )
        os.close(write_fd)
        write_fd = -1

        # _read_with_deadline() always closes its fd - stop looking owned here
        # first, or a raise would make the outer finally double-close it.
        fd_to_read, read_fd = read_fd, -1
        secret = _read_with_deadline(fd_to_read, timeout_sec)
        if not secret:
            raise KeyringUnavailable("Secret portal returned no data (denied or unsupported)")
        return secret
    except GLib.Error as exc:
        raise KeyringUnavailable(f"Secret portal call failed: {exc}") from exc
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def _encryption_key() -> bytes:
    global _cached_key, _key_unavailable
    if _key_unavailable:
        raise KeyringUnavailable("Secret portal was unavailable earlier this session")
    if _cached_key is None:
        try:
            _cached_key = hashlib.sha256(_retrieve_portal_secret()).digest()
        except KeyringUnavailable:
            _key_unavailable = True
            raise
    return _cached_key


def warm_cache() -> None:
    """Pay the first (possibly slow) portal round trip now, off the UI thread,
    so later store_token/load_token calls hit the cache instead of blocking."""
    try:
        _encryption_key()
    except KeyringUnavailable:
        pass


def _require_crypto() -> None:
    if not _HAS_CRYPTO:
        raise KeyringUnavailable("libcrypto (OpenSSL) is not available")


def _load_secrets_file() -> dict:
    path = _secrets_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_secrets_file(secrets: dict) -> None:
    """Write via a temp file + atomic rename so a crash mid-write can't
    corrupt every stored credential at once."""
    path = _secrets_path()
    tmp_path = path + ".tmp"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(secrets, f)
    os.replace(tmp_path, path)


def store_token(form_name: str, backend: str, token: dict) -> None:
    """Persist a credential dict (OAuth tokens, WebDAV username/password, ...)."""
    _require_crypto()
    nonce = os.urandom(12)
    plaintext = json.dumps(token).encode("utf-8")
    ciphertext = _aes256gcm_encrypt(_encryption_key(), nonce, plaintext)
    blob = base64.b64encode(nonce + ciphertext).decode("ascii")

    with _file_lock:
        secrets = _load_secrets_file()
        secrets[f"{backend}:{form_name}"] = blob
        _save_secrets_file(secrets)


def load_token(form_name: str, backend: str) -> dict | None:
    _require_crypto()
    raw = _load_secrets_file().get(f"{backend}:{form_name}")
    if raw is None:
        return None
    try:
        blob = base64.b64decode(raw)
        nonce, ciphertext = blob[:12], blob[12:]
        plaintext = _aes256gcm_decrypt(_encryption_key(), nonce, ciphertext)
        return json.loads(plaintext)
    except Exception:
        return None


def clear_token(form_name: str, backend: str) -> None:
    with _file_lock:
        secrets = _load_secrets_file()
        if secrets.pop(f"{backend}:{form_name}", None) is not None:
            _save_secrets_file(secrets)


def is_available() -> bool:
    return _HAS_CRYPTO
