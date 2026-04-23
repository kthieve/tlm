"""Parallel Lightpanda fetch batches + live terminal progress (Rich + plain fallback)."""

from __future__ import annotations

import re
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

# argv → (exit_code, combined stdout+stderr)
RunArgvFn = Callable[[list[str]], tuple[int, str]]


@dataclass
class FetchJob:
    key: str
    label: str
    url: str
    argv: list[str]
    preview: str
    kind: str  # "fetch" | "search"


@dataclass
class FetchResult:
    job: FetchJob
    status: str  # done | error | timeout | declined
    exit_code: int = 0
    body: str = ""
    elapsed_ms: int = 0
    title: str = ""
    snippet: str = ""
    char_count: int = 0
    error: str = ""


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def summarize_fetch_text(body: str, *, dump: str) -> tuple[str, str, int]:
    """
    Heuristic title + snippet for UI / INDEX line.
    dump is "markdown" or "html" (as from web_dump).
    """
    d = (dump or "markdown").lower().strip()
    n = len(body or "")
    if d == "html":
        t = re.search(
            r"<title[^>]*>([^<]+)</title>", body or "", flags=re.IGNORECASE | re.DOTALL
        )
        title = _collapse_ws(t.group(1)) if t else ""
        if not title:
            h = re.search(r"<h1[^>]*>([^<]+)</h1>", body or "", flags=re.IGNORECASE)
            title = _collapse_ws(h.group(1)) if h else ""
        text = re.sub(r"(?s)<script[^>]*>.*?</script>", " ", body or "", flags=re.IGNORECASE)
        text = re.sub(r"(?s)<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = _collapse_ws(text)[:500]
        snippet = text[:300] if text else ""
    else:
        lines = (body or "").splitlines()
        title = ""
        rest_start = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s and not s.startswith("```") and s != "---":
                title = s.lstrip("#").strip()[:200]
                rest_start = i + 1
                break
        if not title:
            title = "(no title line)"
        rest = "\n".join(lines[rest_start:]).strip()
        rest = re.sub(r"^```[\s\S]*?```", " ", rest, count=1)
        rest = _collapse_ws(rest)[:500]
        snippet = rest[:300] if rest else ""
    if not title:
        title = "(untitled page)"
    return title, snippet, n


def _host(url: str) -> str:
    try:
        h = urlparse(url).netloc
        return h or url
    except Exception:
        return url


def _truncate_for_model(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n… (truncated for context limit)\n"


def format_web_feedback(
    results: list[FetchResult],
    *,
    max_chars: int,
) -> str:
    """Build WEB RESULTS INDEX + per-URL command blocks for the LLM."""
    lines: list[str] = ["WEB RESULTS INDEX:"]
    for i, r in enumerate(results, start=1):
        u = r.job.url
        if r.status == "declined":
            lines.append(f"{i}. (declined) — {u}")
        elif r.status in ("error", "timeout"):
            err = r.error or r.status
            lines.append(f"{i}. (failed: {err}) — {u}")
        else:
            lines.append(
                f"{i}. {r.title} — {u} ({r.char_count} chars, exit {r.exit_code})"
            )
    parts: list[str] = ["\n".join(lines), ""]
    for r in results:
        prev = r.job.preview
        if r.status == "declined":
            parts.append(f"User declined web: {r.job.label}\n")
            continue
        if r.status in ("error", "timeout"):
            parts.append(
                f"$ {prev}\n(error: {r.error or r.status})\n"
            )
            continue
        body = _truncate_for_model(r.body, max_chars)
        if r.snippet and r.status == "done":
            parts.append(f"Snippet: {r.snippet}\n")
        parts.append(f"$ {prev}\n{body}\n")
    return "\n".join(parts).strip() + "\n"


def _plain_progress_line(i: int, n: int, phase: str, host: str, extra: str = "") -> None:
    msg = f"[{i}/{n}] {phase:10} {host}"
    if extra:
        msg += f"  {extra}"
    print(msg, file=sys.stderr, flush=True)


def _execute_one(
    job: FetchJob, run_argv: RunArgvFn, dump: str
) -> FetchResult:
    """Run one fetch in a worker thread; map timeouts / errors to FetchResult."""
    t0 = time.perf_counter()
    try:
        _code, body = run_argv(job.argv)  # noqa: S603
        ms = int((time.perf_counter() - t0) * 1000)
        title, snippet, ccount = summarize_fetch_text(body, dump=dump)
        return FetchResult(
            job=job,
            status="done",
            exit_code=_code,
            body=body,
            elapsed_ms=ms,
            title=title,
            snippet=snippet,
            char_count=ccount,
        )
    except Exception as e:  # noqa: BLE001
        ms = int((time.perf_counter() - t0) * 1000)
        name = type(e).__name__
        if name == "TimeoutExpired" or "timeout" in str(e).lower():
            return FetchResult(
                job=job,
                status="timeout",
                elapsed_ms=ms,
                error=f"timeout: {e}",
            )
        return FetchResult(
            job=job,
            status="error",
            elapsed_ms=ms,
            error=f"{name}: {e}"[:500],
            body=traceback.format_exc()[:2000],
        )


def run_web_batch(
    jobs: list[FetchJob],
    *,
    run_argv: RunArgvFn,
    timeout: float,
    env: dict[str, str] | None,  # noqa: ARG001 — for caller; subprocess env set in run_argv
    concurrency: int,
    dump: str,
    max_output_chars: int,  # noqa: ARG001 — applied in format_web_feedback from ask_tools
    pcon,  # rich.console.Console on stderr, or None
    use_rich: bool,
    next_hint: str = "",
) -> list[FetchResult]:
    """
    Run each job's argv in a thread pool; return results in the same order as `jobs`.
    """
    n = len(jobs)
    if n == 0:
        return []

    conc = max(1, min(8, int(concurrency)))
    # Shared state for live table (read by render thread, written by as_completed)
    status = ["queued"] * n
    worker_label = [""] * n
    chars_count = [""] * n
    results: list[FetchResult | None] = [None] * n
    # Track Future.running() for rows still in flight
    future_by_idx: list[object | None] = [None] * n

    def _short_url(u: str) -> str:
        if len(u) <= 64:
            return u
        return u[:30] + "…" + u[-28:]

    def work(idx: int, job: FetchJob) -> tuple[int, FetchResult]:
        return idx, _execute_one(job, run_argv, dump)

    if not use_rich or pcon is None:
        with ThreadPoolExecutor(max_workers=conc) as ex:
            futs2 = {ex.submit(work, i, jobs[i]): i for i in range(n)}
            for fut in as_completed(futs2):
                idx0 = futs2[fut]
                try:
                    idx, r = fut.result()
                    results[idx] = r
                    if r.status == "done" and r.char_count:
                        _plain_progress_line(
                            idx + 1, n, "done", _host(r.job.url), f"{r.char_count} chars"
                        )
                    else:
                        _plain_progress_line(
                            idx + 1, n, r.status, _host(r.job.url)
                        )
                except Exception as e:  # noqa: BLE001
                    results[idx0] = FetchResult(
                        job=jobs[idx0],
                        status="error",
                        error=str(e),
                    )
        return [r if r is not None else FetchResult(jobs[i], "error", error="missing") for i, r in enumerate(results)]  # type: ignore[return-value]

    # Rich Live
    try:
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
    except Exception:
        return run_web_batch(
            jobs,
            run_argv=run_argv,
            timeout=timeout,
            env=env,
            concurrency=concurrency,
            dump=dump,
            max_output_chars=max_output_chars,
            pcon=None,
            use_rich=False,
            next_hint=next_hint,
        )

    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    wslot: list[int] = [0]  # round-robin slot label w1..wN

    def render() -> Panel:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("status", width=9)
        table.add_column("w", style="dim", width=2)
        table.add_column("url", no_wrap=True, overflow="ellipsis", max_width=52)
        table.add_column("chars", width=8)
        for i, job in enumerate(jobs):
            u = _short_url(job.url)
            st = status[i]
            fut = future_by_idx[i]
            if results[i] is not None:
                st = results[i].status  # type: ignore[union-attr]
            elif fut is not None and getattr(fut, "running", lambda: False)():
                st = "running"
            else:
                st = status[i]
            ch = chars_count[i] or "—"
            table.add_row(
                str(i + 1),
                st,
                worker_label[i] or "—",
                u,
                ch,
            )
        sub = f"{n} link(s), {conc} workers"
        if next_hint:
            sub += f" | next: {next_hint[:120]}"
        return Panel(
            table,
            title=f"tlm-web batch ({n} links, {conc} parallel)",
            subtitle=sub,
            border_style="cyan",
        )

    stop_refresh = threading.Event()

    def refresh_loop(live: Live) -> None:
        while not stop_refresh.wait(0.12):
            try:
                live.update(render())
            except Exception:
                break

    with ThreadPoolExecutor(max_workers=conc) as ex:
        for i, job in enumerate(jobs):
            f = ex.submit(work, i, job)
            future_by_idx[i] = f
        with Live(render(), console=pcon, refresh_per_second=8, transient=True) as live:
            ref = threading.Thread(target=refresh_loop, args=(live,), daemon=True)
            ref.start()
            try:
                futs2 = {future_by_idx[i]: i for i in range(n) if future_by_idx[i] is not None}
                for fut in as_completed(futs2):
                    idx = futs2[fut]
                    wslot[0] = (wslot[0] % conc) + 1
                    worker_label[idx] = f"w{wslot[0]}"
                    try:
                        _i, r = fut.result()
                        results[_i] = r
                        if r.status == "done" and r.char_count:
                            chars_count[_i] = f"{r.char_count:,}"[:8]
                        elif r.status in ("error", "timeout"):
                            chars_count[_i] = "err"
                    except Exception as e:  # noqa: BLE001
                        results[idx] = FetchResult(
                            job=jobs[idx],
                            status="error",
                            error=str(e),
                        )
                    status[idx] = results[idx].status  # type: ignore[union-attr]
                    live.update(render())
            finally:
                stop_refresh.set()
                ref.join(timeout=1.0)

    out: list[FetchResult] = []
    for i, r in enumerate(results):
        if r is None:
            r = FetchResult(jobs[i], "error", error="missing result")
        out.append(r)

    pcon.print(
        Panel(
            "\n".join(
                f"{i+1}. [{r.status}] {(r.title or '')[:50]} — {_short_url(jobs[i].url)}"
                for i, r in enumerate(out)
            ),
            title="tlm-web summary (heuristic titles)",
            border_style="green",
        )
    )
    if next_hint:
        pcon.print(f"[dim]Next (model):[/] {next_hint[:400]}")
    return out
