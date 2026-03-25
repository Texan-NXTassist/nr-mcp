# Changelog

## [1.2.0] — 2026-03-25

### Added
- Bearer token authentication (`NR_TOKEN` env var) as alternative to Basic Auth
- `.env.example` with all configuration options
- Comprehensive `README.md` with installation and usage guide
- MIT License

### Changed
- Default `NR_URL` changed from hardcoded IP to `http://localhost:1880`
- Generalized documentation for public use
- Updated `pyproject.toml` with full project metadata and classifiers

### Removed
- Internal development files (`.cursor/rules/`)
- Private infrastructure references from documentation

## [1.1.0] — 2026-03-17

### Added
- `nr_create_nodes` — batch node creation in a single deploy
- `nr_delete_nodes` — batch deletion with automatic wire/group cleanup
- `nr_inject` — trigger inject nodes remotely
- `nr_get_installed_modules` — list installed modules and node types
- `nr_install_module` — install npm packages from the registry
- `nr_get_debug_output` — read debug data from flow context

## [1.0.0] — 2026-03-08

### Added
- Initial release with 7 core tools
- `nr_get_flow_summary` — overview of all tabs
- `nr_get_flow` — get single tab with nodes and groups
- `nr_search_nodes` — search by name, type, or code content
- `nr_get_function_code` — extract JavaScript from function nodes
- `nr_get_node_config` — full config with upstream/downstream connections
- `nr_get_flow_context` — read flow-level context variables
- `nr_safe_deploy` — deploy with optimistic locking (GET\u2192POST, never PUT)
- Correct Node-RED Admin API v2 usage (fixes tab reorder bug)
- Basic Auth support via environment variables
