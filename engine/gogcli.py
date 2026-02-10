import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class GogResult:
    ok: bool
    data: Any | None = None
    error: str | None = None
    command: list[str] | None = None


def run_gog(
    args: list[str], account: str | None = None, timeout: int = 120
) -> GogResult:
    cmd = ["gog"]
    if account:
        cmd.append(f"--account={account}")
    # JSON output and non-interactive for deterministic discovery.
    cmd += ["--json", "--no-input"]
    cmd += args

    try:
        p = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        out = p.stdout.strip()
        data = json.loads(out) if out else None
        return GogResult(ok=True, data=data, command=cmd)
    except subprocess.CalledProcessError as e:
        return GogResult(
            ok=False, error=(e.stderr or e.stdout or str(e)).strip(), command=cmd
        )
    except subprocess.TimeoutExpired:
        return GogResult(ok=False, error=f"timeout after {timeout}s", command=cmd)
    except json.JSONDecodeError as e:
        return GogResult(
            ok=False, error=f"failed to parse JSON output: {e}", command=cmd
        )
