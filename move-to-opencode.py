#!/usr/bin/env python3
"""Hand the current Claude Code session over to opencode.

Converts this session's transcript to markdown, saves it under
~/.claude/handoffs/, and starts a headless opencode session in the same working
directory with the transcript attached. It is titled with the session's name in
Claude Code, else Claude's own title for it, else a short title generated from
the first messages.
Resume it with `opencode --session <id>`, the session list (ctrl+x l), or a
dashboard like Open Agent View. No terminal window is opened, so it works from
any terminal.

Usage:
  move-to-opencode.py [provider/model] [--session ID] [--no-launch]

The session id defaults to $CLAUDE_CODE_SESSION_ID, which Claude Code sets for
every shell it spawns (including a skill's `!` injection).
"""
import argparse
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

HANDOFF_DIR = os.path.expanduser("~/.claude/handoffs")
OPENCODE = shutil.which("opencode") or os.path.expanduser("~/.opencode/bin/opencode")
TOOL_INPUT_MAX = 800
TOOL_RESULT_MAX = 1500
TITLE_MAX = 60
SESSION_VARS = {"CLAUDE_PID", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT"}
STRIP = re.compile(
    r"<(system-reminder|local-command-caveat|local-command-stdout|command-message)>.*?</\1>",
    re.S,
)


def clip(s, n):
    s = s.strip()
    return s if len(s) <= n else s[:n] + f"\n… [{len(s) - n} more chars truncated]"


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for b in content:
        if b.get("type") == "text":
            parts.append(b["text"])
        elif b.get("type") == "image":
            parts.append("[image]")
    return "\n".join(parts)


def convert(path):
    out, cwd, custom_title, ai_title, asks = [], None, None, None, []
    for line in open(path):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "custom-title":
            custom_title = d.get("customTitle") or custom_title
        if d.get("type") == "ai-title":
            ai_title = d.get("aiTitle") or ai_title
        if d.get("type") not in ("user", "assistant") or d.get("isMeta") or d.get("isSidechain"):
            continue
        cwd = d.get("cwd") or cwd
        content = d["message"]["content"]
        if d["type"] == "user":
            if isinstance(content, list) and all(b.get("type") == "tool_result" for b in content):
                for b in content:
                    res = b.get("content")
                    res = text_of(res) if isinstance(res, list) else str(res or "")
                    tag = "tool error" if b.get("is_error") else "tool result"
                    out.append(f"<{tag}>\n{clip(res, TOOL_RESULT_MAX)}\n</{tag}>\n")
                continue
            msg = STRIP.sub("", text_of(content)).strip()
            if msg:
                label = "Summary of earlier conversation" if d.get("isCompactSummary") else "User"
                out.append(f"## {label}\n\n{msg}\n")
                if label == "User" and not msg.startswith("<"):
                    asks.append(msg)
        else:
            for b in content:
                if b.get("type") == "text" and b["text"].strip():
                    out.append(f"## Assistant\n\n{b['text'].strip()}\n")
                elif b.get("type") == "tool_use":
                    args = json.dumps(b.get("input", {}), ensure_ascii=False)
                    out.append(f"**tool call: {b['name']}** `{clip(args, TOOL_INPUT_MAX)}`\n")
    return "\n".join(out), cwd, custom_title or ai_title, asks


def first_clause(text):
    text = re.sub(r"[`*_#>\[\]]", "", text.strip().splitlines()[0])
    text = re.split(r"(?<=[.!?:;])\s|\s[-–—]\s", text)[0].rstrip(".!?:; ")
    if len(text) <= TITLE_MAX:
        return text
    return text[:TITLE_MAX].rsplit(" ", 1)[0]


def generate_title(asks):
    """A short title written by Claude Haiku from the user's own messages,
    or their first clause when Claude is unavailable."""
    if not asks:
        return None
    sample = clip("\n\n".join(asks[:3]), 2000)
    claude = shutil.which("claude")
    if claude:
        # Without the parent session's variables, its SessionEnd hooks (such as
        # a reaper keyed on CLAUDE_PID) act on this throwaway call, not the parent.
        env = {k: v for k, v in os.environ.items() if k not in SESSION_VARS}
        try:
            r = subprocess.run(
                [claude, "-p", "--model", "haiku", "--no-session-persistence",
                 "--tools", "", "--strict-mcp-config",
                 "Write a title of 3 to 6 words for a coding session that began with the "
                 "messages below. Sentence case, no quotes, no trailing punctuation. "
                 "Reply with the title only.\n\n" + sample],
                env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=45,
            )
            title = r.stdout.strip().strip("\"'").rstrip(".")
            if r.returncode == 0 and title and "\n" not in title and len(title) <= TITLE_MAX:
                return title
        except (OSError, subprocess.TimeoutExpired):
            pass
    return first_clause(asks[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    ap.add_argument("model", nargs="?", help="opencode model, e.g. anthropic/claude-sonnet-5-5")
    ap.add_argument("--no-launch", action="store_true", help="write the handoff, print the command")
    a = ap.parse_args()
    if not a.session:
        sys.exit("no session id: pass --session or run inside Claude Code")

    matches = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{a.session}.jsonl"))
    if not matches:
        sys.exit(f"no transcript found for session {a.session}")
    body, cwd, title, asks = convert(matches[0])
    cwd = cwd if cwd and os.path.isdir(cwd) else os.getcwd()

    os.makedirs(HANDOFF_DIR, exist_ok=True)
    handoff = os.path.join(HANDOFF_DIR, f"{a.session}.md")
    with open(handoff, "w") as f:
        f.write(f"# Claude Code session {a.session}\n\nWorking directory: {cwd}\n\n{body}")

    prompt = (
        "This continues a Claude Code session; the attached file is its full transcript "
        "(user messages, assistant replies, tool calls; long tool output is truncated). "
        "Read it, then tell me in 2-3 lines where we left off and what the next step is. "
        "Do not start working until I say so."
    )
    title = title or generate_title(asks) or "Continued Claude Code session"
    cmd = [OPENCODE, "run", "--dir", cwd, "--title", title, "-f", handoff]
    cmd += (["--model", a.model] if a.model else []) + ["--", prompt]

    kb = os.path.getsize(handoff) // 1024
    if a.no_launch:
        print(f"handoff: {handoff} ({kb} KB)\ncwd: {cwd}\n{shlex.join(cmd)}")
        return
    # Detached so it outlives this Claude Code turn; it exits once the model has replied.
    log = open(handoff[:-3] + ".opencode.log", "w")
    subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    print(f'started opencode session "{title}" in {cwd}; it appears in the opencode session list once the model replies')


if __name__ == "__main__":
    main()
