# Deployment and Reliability for WPF Products

## Contents

- Publish modes
- Runtime identifiers and architectures
- Installer design
- Updates and rollback
- Configuration and secrets
- Logging and diagnostics
- Startup, shutdown, and recovery
- Offline and degraded operation
- Operational readiness checklist

## Publish modes

Choose publish mode based on deployment control and support requirements:

- **Framework-dependent**: smaller output, but requires a compatible runtime on the machine.
- **Self-contained**: includes the runtime and provides more deterministic deployment at a larger size.
- **Single-file**: simplifies distribution but can change native library and extraction behavior; validate every dependency.
- **ReadyToRun**: may improve startup at the cost of package size and build time; measure before adopting.
- **Trimmed**: do not enable by default for WPF. Reflection, XAML, serializers, and libraries may require annotations or preservation rules.

Do not combine deployment switches without validating startup, resources, native libraries, and updates on a clean machine.

## Runtime identifiers and architectures

Publish only supported targets, commonly `win-x64` and optionally `win-arm64`. Add `win-x86` only for a real dependency or installed base.

Verify:

- native DLL architecture
- COM registration and bitness
- vendor SDK support
- driver and device compatibility
- installer architecture detection
- update channel separation by architecture

Avoid `AnyCPU` assumptions when native dependencies exist.

## Installer design

The installer should define:

- per-user or per-machine scope
- elevation requirements
- install directory and write permissions
- service, driver, protocol, firewall, and shortcut changes
- prerequisites
- repair and uninstall behavior
- log locations
- code signing

Keep mutable data out of the installation directory. Use appropriate application-data locations with explicit retention and backup policy.

Test fresh install, upgrade, repair, uninstall, and interrupted installation.

## Updates and rollback

Use an external updater or installer transaction when the running executable cannot replace itself atomically.

Define:

- signed update manifest and package verification
- channel and version policy
- download resume and integrity validation
- preflight checks for disk space, permissions, process state, and database compatibility
- atomic switch or transactional install
- health check after update
- automatic or operator-triggered rollback
- retention and cleanup of prior versions

Do not delete the previous working version before the new version passes its health check.

Separate application rollback from data rollback. A binary rollback is unsafe if the database or file format is no longer backward compatible.

## Configuration and secrets

Layer configuration intentionally:

1. product defaults
2. machine or site configuration
3. environment-specific deployment configuration
4. user preferences
5. command-line or support overrides when allowed

Validate configuration at startup and report actionable errors. Redact secrets in logs and support bundles.

Do not store credentials, API keys, or signing material in source control or plain-text user settings. Use Windows-protected storage, a secure enterprise secret mechanism, or an authenticated service as appropriate.

## Logging and diagnostics

Use structured logs with:

- timestamp and level
- application and build version
- process, machine, and session identifiers when permitted
- operation and correlation identifiers
- exception type and stack
- external endpoint or device identifier
- duration and result

Implement retention, size limits, and privacy rules. Avoid synchronous network logging on the UI thread.

A support bundle may include logs, sanitized configuration, version information, environment diagnostics, and recent update history. Require user review or policy approval before including sensitive data.

## Startup, shutdown, and recovery

Startup should:

- establish single-instance behavior when required
- validate configuration and storage
- run bounded migrations
- initialize critical services in dependency order
- expose progress for long operations
- enter degraded mode or fail clearly according to product requirements

Shutdown should:

- disable new commands
- request cancellation
- stop device and network operations
- flush durable state and bounded logs
- stop hosted services
- dispose the host
- exit within an operational timeout

Do not rely on finalizers for important state or device shutdown.

For crash recovery, distinguish:

- unsaved user work
- resumable operations
- in-flight external commands
- partially applied database or update transactions
- corrupted local cache

Use journals or idempotency keys when an operation must be reconciled after restart.

## Offline and degraded operation

Define offline behavior explicitly:

- which features remain available
- how cached data is marked and expired
- how queued operations are persisted and replayed
- how conflicts are resolved
- how the user sees connection and synchronization state
- when safety requires blocking an operation

Do not present stale or simulated data as live data.

## Operational readiness checklist

- Can a clean machine install and launch the product?
- Is the runtime deployment model explicit?
- Are all native dependencies included and architecture-correct?
- Are artifacts and update manifests signed and verified?
- Can updates fail without destroying the working version?
- Is data backward compatible with rollback?
- Are configuration errors actionable?
- Are secrets protected and logs redacted?
- Are logs bounded and supportable?
- Does startup handle unavailable dependencies?
- Does shutdown cancel and dispose all owned work?
- Can operators diagnose version, configuration, update, and external-connection state?
