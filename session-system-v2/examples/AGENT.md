# AGENT.md — TaskFlow

This file defines the engineering standards, environment constraints, and verification gates for TaskFlow.

**Checked into repo:** `TaskFlowOrg/taskflow/AGENT.md`
**Updated:** Session 4
**Scope:** Backend (Python) and Frontend (React/TypeScript)

---

## Environment

**Language & Runtime:**
- Backend: Python 3.12
- Frontend: Node.js 20.x (with pnpm 8.x)
- Database: PostgreSQL 15.x (local Docker container)

**Key Dependencies:**
- Backend: FastAPI 0.109.x, SQLAlchemy 2.0, Alembic, argon2-cffi, PyJWT, slowapi
- Frontend: React 18.x, TypeScript 5.x, Vite, React Router v6, axios

**Shared Environment:**
- Developer Mac (Darwin ARM) and CI/CD Linux x86 share the same `taskflow` folder
- `.venv/` and `node_modules/` are platform-specific; binaries are incompatible between Mac and Linux
- **Sandbox rule:** Linux sandbox CANNOT run `uv sync`, `pip install`, `pnpm install`, `uvicorn`, `vite dev`, or any node/Python package manager. These must run on the Mac.
- **Sandbox CAN:** read files, edit source code, run ruff/mypy/bandit via system Python, run tests via pytest.

**CI/CD:**
- GitHub Actions: linting, type checking, unit tests, security scan (bandit), pre-commit validation
- Pre-commit hooks: ruff (lint + format), bandit, mypy --strict on maintained directories
- Protected files enforcement: `TaskFlowOrg/enforcement` repo manages blessed versions of critical config files

---

## Code Rules

**No-Bypass Rule:** Never add `noqa`, `nosec`, or `# type: ignore` to suppress warnings. Fix the root cause.

### Backend (Python)

1. **No bare except blocks.** All exceptions must be caught explicitly:
   ```python
   # ❌ Bad
   except Exception: pass
   except: pass

   # ✅ Good
   except ValueError as e:
       logging.error(f"Invalid input: {e}")
       return ErrorResponse(code="INVALID_INPUT", message=str(e))
   ```

2. **No silent failures.** Functions must return typed error results, never `{}` or `[]` on failure:
   ```python
   # ❌ Bad
   def get_user(user_id: int):
       try:
           return db.query(User).filter(User.id == user_id).first()
       except:
           return {}  # Hides the error as "no data"

   # ✅ Good
   def get_user(user_id: int) -> User | ErrorResponse:
       try:
           user = db.query(User).filter(User.id == user_id).first()
           if not user:
               return ErrorResponse(code="NOT_FOUND", message=f"User {user_id} not found")
           return user
       except SQLAlchemyError as e:
           logging.error(f"Database error fetching user {user_id}: {e}")
           return ErrorResponse(code="DB_ERROR", message="Failed to retrieve user")
   ```

3. **No f-string SQL.** Always use parameterized queries via SQLAlchemy ORM:
   ```python
   # ❌ Bad
   db.execute(f"SELECT * FROM users WHERE username = '{username}'")

   # ✅ Good
   user = db.query(User).filter(User.username == username).first()
   ```

4. **No `shell=True` in subprocess.** Always use list arguments:
   ```python
   # ❌ Bad
   subprocess.run(f"python {script} {arg}", shell=True)

   # ✅ Good
   subprocess.run(["python", script, arg])
   ```

5. **No unsafe hashing.** Never use `hashlib.md5()`. Use `hashlib.sha256()` or argon2:
   ```python
   # ❌ Bad
   hash_value = hashlib.md5(secret.encode()).hexdigest()

   # ✅ Good
   hash_value = hashlib.sha256(secret.encode()).hexdigest()
   # Or for password hashing:
   from argon2 import PasswordHasher
   ph = PasswordHasher()
   hash_value = ph.hash(password)
   ```

6. **No hardcoded `/tmp`.** Always use `tempfile.gettempdir()`:
   ```python
   # ❌ Bad
   temp_file = "/tmp/taskflow_temp.txt"

   # ✅ Good
   import tempfile
   temp_dir = tempfile.gettempdir()
   temp_file = os.path.join(temp_dir, "taskflow_temp.txt")
   ```

7. **No `urllib.request.urlopen`.** Use `httpx` with `timeout`:
   ```python
   # ❌ Bad
   response = urllib.request.urlopen(url)

   # ✅ Good
   import httpx
   async with httpx.AsyncClient(timeout=30) as client:
       response = await client.get(url)
   ```

8. **Always set `timeout` on HTTP requests.** Prevent hanging connections:
   ```python
   # ❌ Bad
   requests.get(external_url)

   # ✅ Good
   import httpx
   httpx.get(external_url, timeout=30)
   ```

9. **Use `isinstance(x, A | B)` for multiple types.** Modern Python 3.11+ syntax:
   ```python
   # ❌ Bad (Python 3.9 style)
   isinstance(x, (str, bytes))

   # ✅ Good (Python 3.11+)
   isinstance(x, str | bytes)
   ```

### Frontend (React/TypeScript)

1. **No any types.** All functions and components must have explicit types:
   ```typescript
   // ❌ Bad
   const handleClick = (e: any) => {
     console.log(e);
   };

   // ✅ Good
   const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
     console.log(e);
   };
   ```

2. **No silent errors in async operations.** Always catch and log:
   ```typescript
   // ❌ Bad
   fetchTasks().then(setTasks).catch(() => {});

   // ✅ Good
   fetchTasks()
     .then(setTasks)
     .catch((error) => {
       console.error("Failed to fetch tasks:", error);
       setError(error.message);
     });
   ```

3. **No hardcoded API URLs.** Use environment variables:
   ```typescript
   // ❌ Bad
   const API_URL = "http://localhost:8000";

   // ✅ Good
   const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
   ```

---

## Verification Requirements

Before committing, verify all of the following **locally**:

### Backend (Python)

1. **Ruff lint:** `ruff check backend tests/`
2. **Ruff format:** `ruff format --check backend tests/`
3. **Mypy:** `mypy --strict backend/ tests/`
4. **Bandit:** `bandit -r backend/`
5. **Tests:** `pytest tests/ -x` (stops on first failure)
6. **All files staged:** `git add <files>` before committing (prevents stash conflicts)

### Frontend (React/TypeScript)

1. **TypeScript:** `npx tsc --noEmit` (type checking without emit)
2. **Prettier:** `pnpm exec prettier --check src/` (format check)
3. **Tests:** `pnpm test` (vitest or Jest, depending on setup)

### Both

1. **Pre-commit hooks:** `uv run pre-commit run -a` (must pass before push)
2. **No protected file changes:** Verify your branch hasn't modified files in `protected-files.txt` (checked by Enforcement Gate)

### Before Push (Mac Only)

1. Run `npx tsc --noEmit` in `frontend/` to catch TS errors
2. Run `pnpm exec prettier --write <changed files>` on new/modified files
3. Verify `uv run pre-commit run -a` passes repo-wide (catches pre-existing issues)

---

## Git Workflow

**Branches:** Always work on feature branches. Main is protected.

```bash
git checkout -b <type>/<short-description>
# Example: git checkout -b feat/jwt-token-generation
```

**Commits:** Follow conventional commit format:

```
feat: add JWT token generation for auth layer
fix: correct password hash verification timing
refactor: extract database session management
docs: update auth API specification
chore: upgrade FastAPI to 0.110

Body (optional, required for deletions 20+ lines or large scope):

This implements JWT token generation and validation as part of phase-02.
Tokens include user_id, issued_at, and expiry. Expiry strategy is 24 hours
(decided post-discovery of timing attack risk with short-lived tokens).

Token format: Header.Payload.Signature (HS256 with HMAC-SHA256).

Deletion rationale: (if 20+ line removal)
Removed legacy session-based auth in favor of stateless JWT.
Old code in backend/legacy/sessions.py was unused after T3 endpoint migration.

large-change (if significant scope)
```

**Push & PR:**

```bash
git push origin <branch>
gh pr create --title "feat: add JWT token generation" --body "..."
gh pr merge <N> --merge --auto
gh pr checks <N> --watch  # Watch CI before walking away
```

**CI Failure:** If CI fails:
1. Identify the failure (ruff, mypy, bandit, tests)
2. Fix locally, verify with that tool
3. Commit fresh (don't amend)
4. Push and watch CI again

**Force Push:** Only if you amended a commit that's already pushed:
```bash
git push --force-with-lease origin <branch>
```

---

## Session Discipline

1. **Start every session by reading the phase specification** (`plan/phase-NN.yaml`)
2. **Verify the current state** against `state.json` before starting work
3. **Commit frequently:** One task = one commit (or one PR for related sub-tasks)
4. **Document discoveries:** Log issues, blockers, and lessons learned in `sessions/session-NNN.yaml`
5. **Update state.json after PR merge:** Mark tasks complete, update metrics

---

## Enforcement System

TaskFlow uses a two-layer protection system for critical files:

1. **CI Restore:** Before running any checks, GitHub Actions restores blessed copies of protected files (defined in `TaskFlowOrg/enforcement/protected-files.txt`)
2. **Enforcement Gate:** An independent workflow in the enforcement repo blocks PRs that modify protected files

**What this means for you:**
- If your branch changes a protected file, that's okay. CI will ignore your version and use the blessed copy.
- If you need to change a protected file, tell the maintainer. They'll run the blessing workflow.
- Never manually copy files around. CI handles versioning.

---

## Common Issues & Fixes

### Pre-commit stash conflicts

**Symptom:** `fatal: Your local changes to the following files would be stashed` when running pre-commit.

**Fix:** Stage ALL modified files before committing:
```bash
git add backend/routes/auth.py backend/lib/auth.py backend/tests/...
git commit -m "feat: add auth layer"
```

Pre-commit caches formatted state. Unstaged files break the cache.

### Mypy strict mode failures

**Symptom:** `error: Need type annotation for variable "x"` or `Unsupported operand types`

**Fix:** Add explicit types:
```python
# ❌ Bad
user = db.query(User).first()

# ✅ Good
user: User | None = db.query(User).first()
```

### Bandit security findings

**Symptom:** Bandit flags `B310 (urllib.request.urlopen)`, `S113 (missing timeout)`, etc.

**Fix:** Don't suppress. Change the code:
```python
# Use httpx instead, always set timeout
import httpx
response = httpx.get(url, timeout=30)
```

### Type checking errors with async

**Symptom:** `Incompatible types in return` for async functions

**Fix:** Declare return type explicitly:
```python
async def fetch_user(user_id: int) -> User | None:
    return await db.fetch_one(User, user_id)
```

---

## Documentation Files

These files must be kept in sync after every meaningful change:

- **state.json** — Current project state (phases, tasks, metrics, blockers)
- **plan/index.yaml** — Master phase index
- **plan/phase-NN.yaml** — Detailed specification for each phase
- **sessions/session-NNN.yaml** — Work record for each session

After committing code, update the relevant documentation. If a phase completes, update `state.json` and `plan/index.yaml`. If you discover a blocking issue, log it in `state.json` and the session record.

---

## Questions?

Check `sessions/session-004.yaml` for a concrete example of how this is applied in practice.
