# claude-to-opencode

A Claude Code slash command that moves the current session over to [opencode](https://opencode.ai), so you can keep going on a different model or subscription without copy-pasting `/export` output.

```
/move-to-opencode                       # continue on your default opencode model
/move-to-opencode cursor/claude-fable-5-1   # or pick one
```

What it does:

1. Converts the session's transcript (`~/.claude/projects/*/<session-id>.jsonl`) to markdown: user messages, assistant replies and tool calls. Thinking blocks are dropped, long tool output is truncated, and `<system-reminder>` noise is stripped.
2. Saves it to `~/.claude/handoffs/<session-id>.md`.
3. Runs `opencode run --dir <session cwd> --title "<claude title> (from Claude Code)" -f <transcript>` in the background. The new session reads the transcript, summarizes where you left off, and waits for you.

It never opens a terminal window, so it works from any terminal. Pick the session up in opencode's session list (`ctrl+x l`), or in a multi-agent dashboard like [Open Agent View](https://open-agent-view.github.io/) with `oav --include-external`.

## Install

```sh
git clone https://github.com/moritzWa/claude-to-opencode
cd claude-to-opencode
./install.sh                          # installs /move-to-opencode
./install.sh move-to-cursor-opencode  # or under another name
```

Requires Python 3 and `opencode` on your PATH. Start a new Claude Code session after installing so it picks up the command.

## Using a Cursor subscription in opencode

This is what I built it for. The community plugin [cursor-opencode-provider](https://github.com/EpicEric/cursor-opencode-provider) exposes your Cursor models in opencode:

```jsonc
// ~/.config/opencode/opencode.jsonc
{
  "plugin": ["cursor-opencode-provider"],
  "provider": {
    "cursor": {
      "npm": "cursor-opencode-provider",
      "name": "Cursor",
      "models": {},
      "blacklist": ["grok-4.6", "grok-4.6-fast"]  // hide models you don't want in /models
    }
  }
}
```

Then `opencode auth login --provider cursor`, in a real terminal since the login menu needs arrow keys. It talks to Cursor's private API, so it can break when Cursor changes things.

## License

MIT
