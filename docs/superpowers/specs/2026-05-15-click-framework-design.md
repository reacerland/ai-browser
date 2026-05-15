# Design: Migrate auto-browser CLI from argparse to Click

## Context

`cli.py` uses `argparse` to define 10 subcommands + 1 hidden internal command. The help output is sparse and hard to read. `cmd_action()` uses a long `hasattr` chain to dispatch parameters generically, which is fragile boilerplate.

## Decision

Replace `argparse` with [Click](https://click.palletsprojects.com/) (v8.1+). Click provides clear formatted help output per subcommand with minimal code.

## Scope

- **In scope**: `cli.py` rewrite, `pyproject.toml` dependency update
- **Out of scope**: `daemon.py`, `client.py`, other modules; command names or output format changes

## Architecture

```
@click.group()  --session/-s
├── open       URL  --headed
├── close
├── snapshot        --compact --selector
├── click       REF  --double
├── type        REF TEXT  --clear
├── fill        REF VALUE
├── scroll      DIRECTION  --amount
├── screenshot       --output/-o
├── eval        EXPRESSION
├── ping
└── _daemon  (hidden=True)
```

## Key Changes

1. Add `click>=8.1` to `pyproject.toml` dependencies
2. Each subcommand becomes a `@cli.command()` decorated function, replacing `sub.add_parser()` blocks
3. `--session/-s` is a group-level option, passed to subcommands via `@click.pass_context` and `ctx.obj["session"]`
4. `_daemon` subcommand uses `hidden=True` to hide from help output
5. Python function names `click_cmd` and `type_cmd` avoid shadowing Click's `click` module; CLI command names remain `click` and `type`
6. Remove `cmd_action()` — each command calls `client.call()` directly, eliminating the `hasattr` chain

## Preserved Behavior

- All command names, argument names, and flag names unchanged
- JSON output format unchanged (`{"status": "ok", "data": ...}` to stdout, content to stderr)
- `_daemon` internal command unchanged
- `pyproject.toml` `[project.scripts]` entry point unchanged: `ab = "auto_browser.cli:main"`
- `__main__.py` unchanged (delegates to `main()`)

## Removed Code

- `cmd_action()` generic handler with `hasattr` chains
- `argparse` parser construction boilerplate
- `cmd_open()`, `cmd_close()` separate functions (logic moves into Click command functions)
