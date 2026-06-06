# Tool conventions — life-os

> Reference, read once. The orchestration tools used to run the team are **deferred** — load their schemas once per session, then they behave like normal tools. CLAUDE.md §3/§4 reference this file; you don't need it open during normal work.

## Load deferred tools (once per session, before first use)

Orchestration tools are NOT callable until their schema is loaded — calling one cold → `InputValidationError`. Load once:

```
ToolSearch  query: "select:SendMessage,TaskCreate,TaskUpdate,TaskList,TeamCreate"
```

Always-available (no loading): `Agent`, `Read`, `Edit`, `Write`, `Bash`, `ToolSearch`, `ScheduleWakeup`.

Chrome MCP (`mcp__claude-in-chrome__*`, tester + frontend self-verify only): load per tool, e.g. `ToolSearch select:mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__read_console_messages`.

## Verified signatures (use exactly)

| Tool | Key params | Use |
|---|---|---|
| `TeamCreate` | `team_name` (required), `description` | team-lead creates the team once at project start |
| `Agent` | `subagent_type:"<role>"`, `name:"<role>"`, `team_name`, `prompt` | spawn a persistent teammate joining the team (name + team_name = persistent; omit both = one-shot subagent) |
| `SendMessage` | `to:"<name>"`, `message` (string), `summary` (5-10 words, required when message is a string) | the ONLY way to talk to a teammate — plain text output is invisible to them |
| `TaskCreate` | `subject`, `description` | create a unit of work (no owner yet) |
| `TaskUpdate` | `taskId`, `owner`, `status:"pending"\|"in_progress"\|"completed"`, `addBlockedBy` | assign (set `owner`), progress, chain deps |
| `TaskList` | *(none)* | see available/blocked work |

## Conventions

- Refer to teammates by NAME exactly: `team-lead` / `architect` / `backend` / `frontend` / `tester`. No aliases.
- Progress tracked via `TaskUpdate` (not JSON status messages in SendMessage).
- Shutdown a teammate ONLY on explicit user request — via `SendMessage message:{type:"shutdown_request"}`.
