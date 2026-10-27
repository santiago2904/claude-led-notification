# Using led-notify with other coding agents

The daemon doesn't care which agent talks to it. Any tool that can run a shell command on an event can drive the strip with:

```
python3 ~/.config/claude-led/led.py send thinking|done|attention
```

`send` prints nothing, ignores stdin, never fails and gives up after 0.5 s, so it's safe as a hook in any harness.

**Before you start**

1. Configure the strip once. Either run `/led-setup` in Claude Code, or use the script directly (`scan`, `probe`, `test`, as in the README).
2. Start the daemon. On macOS, `python3 scripts/led.py autostart` also copies the script to `~/.config/claude-led/led.py`, the stable path the snippets below use.
3. Without autostart, replace that path with the absolute path to `scripts/led.py` in your clone.

| Harness | thinking | done | attention | Tested |
| --- | --- | --- | --- | --- |
| Claude Code | `UserPromptSubmit` | `Stop` | `Notification` | ✅ plugin |
| GitHub Copilot CLI | `userPromptSubmitted` | `agentStop` | `notification` | ✅ v1.0.36 |
| OpenAI Codex CLI | `UserPromptSubmit` | `Stop` | `PermissionRequest` | docs only |
| Gemini CLI | `BeforeAgent` | `AfterAgent` | `Notification` | docs only |
| Cursor | `beforeSubmitPrompt` | `stop` | — | docs only |
| OpenCode | — | `session.idle` | `permission.asked` | docs only |

"docs only" means the snippet follows the harness's official docs (checked 2026-10) but hasn't been run against a real strip yet. PRs confirming them are welcome.

## GitHub Copilot CLI

Create the file `~/.copilot/hooks/led-notify.json` ([docs](https://docs.github.com/en/copilot/reference/hooks-configuration)):

```json
{
  "version": 1,
  "hooks": {
    "userPromptSubmitted": [{ "type": "command", "bash": "python3 ~/.config/claude-led/led.py send thinking", "timeoutSec": 5 }],
    "agentStop": [{ "type": "command", "bash": "python3 ~/.config/claude-led/led.py send done", "timeoutSec": 5 }],
    "notification": [{ "type": "command", "bash": "python3 ~/.config/claude-led/led.py send attention", "timeoutSec": 5 }]
  }
}
```

## OpenAI Codex CLI

Create the file `~/.codex/hooks.json` ([docs](https://learn.chatgpt.com/docs/hooks)). Codex adds plain stdout from `UserPromptSubmit` to the model's context, and `send` prints nothing, so that's fine.

```json
{
  "hooks": {
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python3 ~/.config/claude-led/led.py send thinking", "timeout": 5 }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "python3 ~/.config/claude-led/led.py send done", "timeout": 5 }] }],
    "PermissionRequest": [{ "hooks": [{ "type": "command", "command": "python3 ~/.config/claude-led/led.py send attention", "timeout": 5 }] }]
  }
}
```

## Gemini CLI

Add this to the file `~/.gemini/settings.json` ([docs](https://geminicli.com/docs/hooks/)):

- Gemini parses hook stdout as JSON, so each command ends with `echo '{}'`.
- `timeout` is in milliseconds.

```json
{
  "hooks": {
    "BeforeAgent": [{ "hooks": [{ "type": "command", "command": "python3 ~/.config/claude-led/led.py send thinking; echo '{}'", "timeout": 5000 }] }],
    "AfterAgent": [{ "hooks": [{ "type": "command", "command": "python3 ~/.config/claude-led/led.py send done; echo '{}'", "timeout": 5000 }] }],
    "Notification": [{ "matcher": "ToolPermission", "hooks": [{ "type": "command", "command": "python3 ~/.config/claude-led/led.py send attention; echo '{}'", "timeout": 5000 }] }]
  }
}
```

Some Gemini CLI versions also need `"tools": { "enableHooks": true }` before hooks run.

## Cursor

Create the file `~/.cursor/hooks.json` ([docs](https://cursor.com/docs/agent/hooks)):

- Cursor has no "needs attention" event.
- `beforeSubmitPrompt` must answer `continue: true`, or Cursor blocks the prompt.

```json
{
  "version": 1,
  "hooks": {
    "beforeSubmitPrompt": [{ "command": "python3 ~/.config/claude-led/led.py send thinking; echo '{\"continue\":true}'", "timeout": 5 }],
    "stop": [{ "command": "python3 ~/.config/claude-led/led.py send done", "timeout": 5 }]
  }
}
```

## OpenCode

Create the plugin file `~/.config/opencode/plugins/led.js` ([docs](https://opencode.ai/docs/plugins/)). OpenCode has no documented "prompt submitted" event, so there is no thinking state.

```js
export const Led = async ({ $ }) => ({
  event: async ({ event }) => {
    const preset = event.type === "session.idle" ? "done"
                 : event.type === "permission.asked" ? "attention" : null;
    if (preset) await $`python3 ${process.env.HOME}/.config/claude-led/led.py send ${preset}`.quiet().nothrow();
  },
});
```

## Anything else

If your tool can run a command, call `led.py send <preset>`. Any Unix-socket client works too:

```
echo "flash 0 255 0 2" | nc -U ~/.config/claude-led/led.sock
```
