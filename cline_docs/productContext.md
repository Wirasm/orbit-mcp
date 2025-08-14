# Orbit-MCP — Product Context
Last Updated: 2025-08-09

Purpose
- Orbit-MCP is a meta-orchestrator (control plane) for the MCP ecosystem that lets teams centrally discover, enable, authenticate, and govern many MCP servers (147+) through one interface. It reduces per-developer setup toil and provides a consistent, secure tool layer for AI coding assistants and agents.

Why We’re Building This
- Fragmentation: Teams currently configure MCP servers ad-hoc per developer or per machine. This is slow, error-prone, and not scalable.
- Governance gap: There’s no unified way to enforce OAuth, RBAC, permissions, and audit across tool usage by AI assistants.
- Agent-first dev: As agents become contributors, organizations need a secured, observable path to real tools (GitHub, Notion, Slack, GDrive, etc.).
- Ecosystem timing: Docker’s MCP Gateway standardized server execution and packaging, but enterprises still need org-level control, user management, and visibility.

Core Users and Problems
- Developer teams
  - Problem: Time-consuming, inconsistent setup of 3–10 integrations; brittle local configs; unclear auth; opaque failures.
  - Need: “Turnkey” packs that enable common stacks and get agents productive quickly.
- Platform/DevEx/Eng leaders
  - Problem: No centralized policy, audit, or permission model for agent tool usage; difficult to onboard/remove users; compliance risks.
  - Need: Org-level control plane: packs, OAuth policy, RBAC, audit logs, usage analytics.
- Individual developers
  - Problem: Just want tools to work across devices/editors.
  - Need: Quick discovery, easy auth, minimal local config.

Solutions and Differentiators
- Meta-orchestrator: Manage Docker MCP servers via a single MCP server (“manage the managers”).
- Packs: Curated sets of servers (frontend/backend/devops/data/productivity/web-scraping) to accelerate onboarding and standardize stacks.
- OAuth-first: Handle OAuth flows where supported (GitHub, GDrive) and plan for an OAuth Proxy for services needing proprietary auth (Notion, Slack).
- Gateway lifecycle: Start/stop/status of Docker MCP Gateway; discover and call tools via CLI.
- Team direction (roadmap): RBAC, team permissions, audit logging, dashboards, usage analytics.

Key Workflows (Happy Paths)
- Discovery → Enablement
  - list_available_servers → check_server_auth → authorize_oauth (if needed) → enable_server → list_enabled_tools
- Gateway execution
  - start_gateway → discover_gateway_tools → call_gateway_tool
- Packs
  - create_pack → install_pack (enables servers + reports auth requirements) → get_pack_info → uninstall_pack
- Org/Team (roadmap)
  - Set up org → invite users → assign packs → per-user OAuth association → usage/audit visibility

Product Direction and Priorities
- Wedge (now)
  - Make “packs + OAuth + gateway” delightful and reliable.
  - Deliver a few end-to-end packs that work out of the box and demonstrably reduce setup time.
- Next (near term)
  - OAuth Proxy MVP for services without Docker MCP OAuth (start with Notion, then Slack).
  - Minimal org/user model and secure token storage behind a thin service; inject tokens at call-time.
  - Basic usage and audit logging to build trust and show value.
- Later (enterprise)
  - RBAC, admin dashboard, SSO/SAML (WorkOS), multi-tenant storage and RLS (Supabase), deep audit and analytics.

Personas and Value Propositions
- Eng Managers / DevEx
  - Value: Standardized tool access for agents in minutes; governance and visibility; reduced onboarding cost.
- Senior developers
  - Value: Packs unify the stack across repos/projects; reduced friction and “missing tool” incidents.
- Security/compliance
  - Value: Centralized auth policy; audit trail; token isolation and rotation plan.

Success Metrics (leading indicators)
- Activation: Org connects ≥3 services and makes ≥20 successful tool calls in week 1.
- Time-to-first-call: Median <10 minutes from install to successful authenticated call.
- Retention: ≥50% weekly active orgs in first month.
- Pack adoption: ≥2 packs installed per active org; ≥1 pack modification per month.
- Admin usage: ≥2 admin operations (assign pack / enable server / auth config) per org/month.

Risks and Assumptions
- Docker MCP CLI/API churn could break parsing.
- OAuth coverage limited; many servers rely on API keys/secrets.
- MCP adoption trajectory impacts demand timing.
- Security posture must satisfy early enterprise design partners.

Mitigations
- Encapsulate docker CLI parsing; add integration tests; track versions.
- Deliver OAuth Proxy for Notion/Slack to extend coverage; support managed secrets where OAuth not possible.
- WorkOS + Supabase architecture for user/org, SSO/SAML, RLS, encrypted token storage.
- Provide real, working packs with smoke tests to demonstrate value quickly.

Pricing and Packaging Hypothesis
- Free: Individuals (1 user, 2 integrations, no audit).
- Team ($9–$15/user/mo): Packs, basic audit, limited OAuth Proxy.
- Business ($25–$49/user/mo): RBAC, advanced audit, SSO, custom packs.
- Enterprise: SAML/SCIM, DLP, SLAs, deployment options.

Key Documents (see cline_docs/)
- activeContext.md — Current focus, issues, next steps, live backlog.
- systemPatterns.md — Architecture and data flow; gateway and OAuth proxy patterns.
- developmentWorkflow.md — How we work, testing, release.
- operationalContext.md — Runtime, observability, error handling, SLOs.
- projectBoundaries.md — Constraints, non-negotiables, scale targets.
- techContext.md — Tech stack, libraries, integration choices.

Cross-References
- Code: src/orbit_mcp/mcp_server.py (tools), src/orbit_mcp/pack_manager.py (packs)
- Ideas: ideas/ENTERPRISE_OAUTH_PLAN.md, ideas/WORKOS_SUPABASE_ARCHITECTURE.md
- Packs: packs/oauth-demo.yaml
