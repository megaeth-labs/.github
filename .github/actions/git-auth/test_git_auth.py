"""Exercise real Git HTTPS clone, nested submodules, push and failure cleanup.

The loopback CONNECT proxy terminates TLS with a test-only github.com certificate
and serves git-http-backend. No real GitHub credentials or network are used.
"""
import base64
import os
from pathlib import Path
import socketserver
import ssl
import subprocess
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parent
TOKEN = "fixture-token-never-persist"


def run(*args, cwd=None, env=None, check=True):
    return subprocess.run(args, cwd=cwd, env=env, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class GitProxy(socketserver.StreamRequestHandler):
    def handle(self):
        connect = self.rfile.readline().decode().strip()
        while self.rfile.readline() != b"\r\n":
            pass
        if connect != "CONNECT github.com:443 HTTP/1.1":
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        self.wfile.flush()
        with self.server.tls.wrap_socket(self.connection, server_side=True) as conn:
            request = conn.makefile("rb")
            method, target, _ = request.readline().decode().strip().split(" ", 2)
            headers = {}
            for line in request:
                if line == b"\r\n":
                    break
                key, value = line.decode().split(":", 1)
                headers[key.lower()] = value.strip()
            expected = "Basic " + base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
            if headers.get("authorization") != expected:
                conn.sendall(b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="git"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                return
            body = request.read(int(headers.get("content-length", "0")))
            path, _, query = target.partition("?")
            result = run("git", "http-backend", env={
                **self.server.git_env,
                "GIT_PROJECT_ROOT": str(self.server.repositories),
                "GIT_HTTP_EXPORT_ALL": "1", "PATH_INFO": path,
                "QUERY_STRING": query, "REQUEST_METHOD": method,
                "CONTENT_TYPE": headers.get("content-type", ""),
                "CONTENT_LENGTH": str(len(body)), "REMOTE_USER": "x-access-token",
            }, check=False) if not body else subprocess.run(
                ["git", "http-backend"], input=body, capture_output=True, env={
                    **self.server.git_env, "GIT_PROJECT_ROOT": str(self.server.repositories),
                    "GIT_HTTP_EXPORT_ALL": "1", "PATH_INFO": path,
                    "QUERY_STRING": query, "REQUEST_METHOD": method,
                    "CONTENT_TYPE": headers.get("content-type", ""),
                    "CONTENT_LENGTH": str(len(body)), "REMOTE_USER": "x-access-token",
                })
            response_headers, _, response_body = result.stdout.partition(b"\r\n\r\n")
            status = b"200 OK"
            outgoing = []
            for line in response_headers.split(b"\r\n"):
                if line.lower().startswith(b"status:"):
                    status = line.split(b":", 1)[1].strip()
                else:
                    outgoing.append(line)
            conn.sendall(b"HTTP/1.1 " + status + b"\r\n" + b"\r\n".join(outgoing)
                         + b"\r\nContent-Length: " + str(len(response_body)).encode()
                         + b"\r\nConnection: close\r\n\r\n" + response_body)


class GitAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.home = cls.root / "home"
        cls.home.mkdir()
        cls.base_env = {**os.environ, "HOME": str(cls.home),
                        "RUSTUP_HOME": os.environ.get("RUSTUP_HOME", str(Path.home() / ".rustup")),
                        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test",
                        "GIT_AUTHOR_EMAIL": "test@example.invalid",
                        "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        # Ensure developer auth/config cannot affect the fixture.
        for key in list(cls.base_env):
            if key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_") or key == "GIT_CONFIG_COUNT":
                del cls.base_env[key]
        repos = cls.root / "repos"
        repos.mkdir()
        for name, child in [("leaf", None), ("middle", "leaf"), ("source", "middle")]:
            work = cls.root / name
            run("git", "init", "-q", str(work), env=cls.base_env)
            (work / "file").write_text(name)
            (work / "Cargo.toml").write_text(f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n[lib]\npath = "lib.rs"\n')
            (work / "lib.rs").write_text("pub fn value() -> u8 { 1 }\n")
            run("git", "-C", str(work), "add", "file", "Cargo.toml", "lib.rs", env=cls.base_env)
            run("git", "-C", str(work), "commit", "-qm", "fixture", env=cls.base_env)
            if child:
                run("git", "-c", "protocol.file.allow=always", "-C", str(work), "submodule", "add", "-q", str(repos / f"{child}.git"), "child", env=cls.base_env)
                run("git", "-C", str(work), "config", "-f", ".gitmodules", "submodule.child.url", f"https://github.com/{child}.git", env=cls.base_env)
                run("git", "-C", str(work), "add", ".gitmodules", "child", env=cls.base_env)
                run("git", "-C", str(work), "commit", "-qm", "submodule", env=cls.base_env)
            run("git", "clone", "--bare", "-q", str(work), str(repos / f"{name}.git"), env=cls.base_env)
            run("git", "--git-dir", str(repos / f"{name}.git"), "config", "http.receivepack", "true", env=cls.base_env)
        key, cert = cls.root / "key.pem", cls.root / "cert.pem"
        run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=github.com", "-addext", "subjectAltName=DNS:github.com", "-keyout", str(key), "-out", str(cert))
        cls.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), GitProxy)
        cls.server.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.server.tls.load_cert_chain(cert, key)
        cls.server.repositories = repos
        cls.server.git_env = cls.base_env
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.env = {**cls.base_env, "GITHUB_AUTH_TOKEN": TOKEN,
                   "https_proxy": f"http://127.0.0.1:{cls.server.server_address[1]}",
                   "no_proxy": "", "NO_PROXY": "", "GIT_SSL_CAINFO": str(cert)}
        (cls.home / ".gitconfig").write_text('[credential]\n\thelper = store\n')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def auth(self, *args, **kwargs):
        return run(str(HERE / "with-github-auth.sh"), *args, env=kwargs.pop("env", self.env), **kwargs)

    def assert_no_credentials_on_disk(self):
        self.assertEqual((self.home / ".gitconfig").read_text(), '[credential]\n\thelper = store\n')
        self.assertFalse((self.home / ".git-credentials").exists())
        leaked = [str(p.relative_to(self.root)) for p in self.root.rglob("*")
                  if p.is_file() and TOKEN.encode() in p.read_bytes()]
        self.assertEqual(leaked, [])

    def test_clone_nested_submodules_and_push_without_persisting_credentials(self):
        clone = self.root / "clone"
        result = self.auth("git", "clone", "--recurse-submodules", "https://github.com/source.git", str(clone))
        self.assertEqual((clone / "child/child/file").read_text(), "leaf")
        self.auth("git", "-C", str(clone), "tag", "auth-test")
        self.auth("git", "-C", str(clone), "push", "origin", "refs/tags/auth-test")
        run("git", "--git-dir", str(self.server.repositories / "source.git"), "rev-parse", "refs/tags/auth-test", env=self.base_env)
        self.assertNotIn(TOKEN.encode(), result.stdout + result.stderr)
        self.assert_no_credentials_on_disk()

    def test_wrong_token_fails_without_storing_credentials(self):
        result = self.auth("git", "ls-remote", "https://github.com/source.git", env={**self.env, "GITHUB_AUTH_TOKEN": "incorrect"}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_credentials_on_disk()

    def test_child_failure_is_preserved(self):
        result = self.auth("bash", "-c", "exit 42", check=False)
        self.assertEqual(result.returncode, 42)
        self.assert_no_credentials_on_disk()

    def test_existing_checkout_header_and_store_helper_are_ignored_without_mutation(self):
        clone = self.root / "persisted-checkout"
        self.auth("git", "clone", "https://github.com/source.git", str(clone))
        run("git", "-C", str(clone), "config", "credential.helper", "store", env=self.base_env)
        run("git", "-C", str(clone), "config", "http.https://github.com/.extraheader", "AUTHORIZATION: Basic stale", env=self.base_env)
        before = (clone / ".git/config").read_bytes()
        self.auth("git", "-C", str(clone), "ls-remote", "origin")
        self.assertEqual((clone / ".git/config").read_bytes(), before)
        self.assert_no_credentials_on_disk()

    def test_wrapper_preserves_github_step_outputs(self):
        output = self.root / "step-output"
        self.auth("bash", "-c", 'echo remaining_count=2 >> "$GITHUB_OUTPUT"',
                  env={**self.env, "GITHUB_OUTPUT": str(output)})
        self.assertEqual(output.read_text(), "remaining_count=2\n")

    def test_cargo_fetch_with_nested_git_dependency_then_build_without_token(self):
        project = self.root / "cargo-project"
        project.mkdir()
        (project / "Cargo.toml").write_text('[package]\nname="consumer"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="lib.rs"\n[dependencies]\nmiddle={git="https://github.com/middle.git"}\n')
        (project / "lib.rs").write_text("pub fn value() -> u8 { middle::value() }\n")
        cargo_env = {**self.env, "CARGO_HOME": str(self.root / "cargo-home")}
        self.auth("cargo", "generate-lockfile", cwd=project, env=cargo_env)
        self.auth("cargo", "fetch", "--locked", cwd=project, env=cargo_env)
        # No askpass or token is provided to the offline build.
        run("cargo", "build", "--offline", "--locked", cwd=project,
            env={**self.base_env, "CARGO_HOME": cargo_env["CARGO_HOME"]})
        self.assert_no_credentials_on_disk()

    def test_askpass_refuses_other_hosts_and_username_spoofing(self):
        for prompt in ("Password for 'https://x-access-token@evil.example': ",
                       "Password for 'https://github.com@evil.example': ",
                       "Password for 'https://x-access-token@github.com.evil.example': "):
            with self.subTest(prompt=prompt):
                result = run(str(HERE / "askpass.sh"), prompt, env=self.env, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_missing_token_fails_before_running_command(self):
        result = self.auth("bash", "-c", "echo should-not-run", env={**self.env, "GITHUB_AUTH_TOKEN": ""}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
