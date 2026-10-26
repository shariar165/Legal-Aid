@AGENTS.md

Claude Code specifics:
- Use plan mode for any feature; save the approved plan to `docs/specs/` as `YYYY-MM-DD-NN-short-name.md`.
- Project skills live in `.claude/skills/` (`rebuild-corpus`, `warm-cache`).
- MCP: `.mcp.json` registers the Ain MCP server (`python -m ain.mcp_server`, from `backend/`), so you can call
  `search_law`, `get_section` and `verify_citation` while you work on the playbook.
