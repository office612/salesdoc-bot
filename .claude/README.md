# Claude Code configuration for salesdoc-bot

This folder configures design/UI capabilities for Claude Code sessions on this repository
(including Claude Code on the web).

## What's enabled

- **`frontend-design` (official Anthropic plugin)** — enabled via `settings.json`
  (`enabledPlugins`). Gives Claude a design system and philosophy for building distinctive,
  production-grade frontend interfaces. Marketplace: `claude-plugins-official`
  (`anthropics/claude-plugins-official`), registered in `extraKnownMarketplaces`.
  Activates automatically when you ask Claude to build UI, pages, or components.

- **`web-design-guidelines` skill** (`skills/web-design-guidelines/`) — vendored from
  Vercel's open-source agent-skills (MIT). Reviews UI code against the Web Interface
  Guidelines. Ask things like "review my UI" or "audit the design".

## Scope note

This configuration applies **only to this repository**. To get the same plugins/skills in
ALL your projects, install them globally in your local Claude Code:

- Anthropic frontend-design: run `/plugin` and install `frontend-design` to **User** scope.
- Vercel skills: `npx skills add vercel-labs/agent-skills`

## Not included (unverified)

The marketing posts also advertised plugins from individual creators
(`nextlevelbuilder`, `claudekit/...-demo`, `Dammyjay93`, `LeonxInx`). These come from
third-party accounts and were not verified for safety, so they are intentionally left out —
plugins can run arbitrary code with your privileges.
