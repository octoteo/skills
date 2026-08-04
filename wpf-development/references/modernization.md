# Modernizing Existing WPF Applications

## Contents

- Modernization goals
- Baseline and inventory
- Migration sequence
- Architecture seams
- UI-thread and asynchronous modernization
- MVVM migration
- Configuration, logging, and hosting
- Persistence and external integrations
- Package and framework upgrades
- Stopping rules

## Modernization goals

Define measurable outcomes before changing structure. Examples:

- target .NET 10 with a clean build
- reduce startup time or UI hangs
- make one critical workflow testable
- isolate a vendor SDK
- add structured logs and crash diagnostics
- support offline startup or safe recovery
- replace an unsafe update mechanism

Do not use a vague goal such as "make the architecture clean" as the sole justification for a rewrite.

## Baseline and inventory

Record:

- current target frameworks and SDK pinning
- build, test, publish, and installer commands
- application startup and shutdown flow
- external packages and unsupported dependencies
- database and configuration formats
- Windows versions and runtime identifiers
- known warnings, crashes, UI freezes, and memory growth
- deployment and rollback path

Create a reproducible baseline before changing target frameworks. If the baseline fails, capture those failures separately.

## Migration sequence

Use small stages that can be built and tested independently:

1. Reproduce the current build.
2. Add or repair automated tests around the highest-risk behavior.
3. Update SDK and target framework.
4. Resolve compiler, XAML, and runtime compatibility.
5. Update packages in coherent groups.
6. Introduce a composition root and logging.
7. Extract external boundaries.
8. Move domain and application logic out of views.
9. Improve cancellation, error handling, and lifecycle management.
10. Modernize packaging and updates.
11. Remove temporary adapters after verification.

Commit or checkpoint at each logical boundary.

## Architecture seams

Introduce seams around unstable or hazardous dependencies first:

- database access
- file system and configuration
- HTTP and message brokers
- PLC, robot, camera, scanner, and serial interfaces
- licensing and authentication
- update and installer logic
- clock and scheduler behavior

Use a wrapper that preserves current behavior before redesigning it. This allows the old and new implementation to be compared.

## UI-thread and asynchronous modernization

Search for:

- `.Result`, `.Wait()`, and synchronous-over-async calls
- synchronous database, file, network, or device calls in event handlers
- long-running constructors
- unbounded dispatcher invocations
- overlapping timers
- fire-and-forget tasks without error observation
- cancellation tokens that are created but not propagated

Modernize one workflow end to end. Define operation state such as idle, running, completed, cancelled, and failed. Disable or serialize duplicate commands where the underlying operation is not reentrant.

Do not convert every method to async mechanically. Keep pure CPU and in-memory methods synchronous.

## MVVM migration

Do not rewrite all views at once.

For each feature:

1. Identify state, commands, and business decisions in code-behind.
2. Move business decisions into an application service.
3. Move bindable state and commands into a view model.
4. Leave view-only behavior in the view.
5. Add tests for the service and view model.
6. Remove obsolete event wiring and subscriptions.

Avoid a base view model with unrelated global services. Prefer constructor injection and feature-specific dependencies.

## Configuration, logging, and hosting

Introduce the Generic Host at the composition root when the product needs standardized DI, configuration, logging, or background services.

Migration steps:

1. Add the host package at a verified .NET 10-compatible version.
2. Move service construction into registrations.
3. Move configuration to typed options where validation adds value.
4. Replace global service locators incrementally.
5. Start and stop background services with application lifetime.
6. Add log scopes around user operations and external calls.

Do not move secrets from source code into plain-text configuration and call the problem solved. Use an appropriate protected store or deployment secret mechanism.

## Persistence and external integrations

Preserve data compatibility unless a controlled migration exists. Before changing a schema or file format, define:

- forward migration
- backup
- failure recovery
- rollback compatibility
- handling for partially migrated state
- disk-full and permission failures

For external devices and services, preserve protocol timing and acknowledgement semantics. Add timeouts and bounded retries only after confirming that duplicate operations are safe.

## Package and framework upgrades

Group upgrades by subsystem and validate after each group. Read release notes for:

- WPF controls and theme libraries
- MVVM packages
- database providers and ORM
- logging sinks
- installers and update frameworks
- vendor SDKs
- testing frameworks

Avoid selecting package versions from memory. Verify official metadata and compatibility with .NET 10.

When a dependency is unsupported, choose explicitly:

- remain on the current framework temporarily
- isolate the dependency behind an out-of-process boundary
- replace the dependency
- maintain a bounded compatibility fork

## Stopping rules

Stop and reassess when:

- the baseline cannot be reproduced
- a required vendor SDK does not support .NET 10
- data rollback cannot be guaranteed for a mandatory migration
- a rewrite removes more verified behavior than it preserves
- the application cannot be validated on its supported Windows environment
- the proposed architecture adds more lifecycle or deployment risk than it removes

A smaller verified modernization is better than an incomplete rewrite.
