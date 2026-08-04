# Architecture for .NET 10 WPF Applications

## Contents

- Architecture tiers
- Project boundaries
- Application lifetime and Generic Host
- MVVM and UI composition
- Navigation and dialogs
- Concurrency and dispatcher rules
- Modules and extensibility
- Data, devices, and external systems
- Error handling and observability
- Architecture review checklist

## Architecture tiers

Choose the least complex tier that meets the product's expected lifetime and change rate.

### Compact

Use one WPF application project plus tests. Organize by feature rather than by technical type when the application is small. Keep domain logic in plain classes even when it shares the application assembly.

Use this tier when:

- the application has a small number of screens
- one team owns the whole product
- deployment is simple
- independent modules are not required
- the expected lifetime and integration surface are limited

### Product

Use these default boundaries:

- `Product.App`: WPF views, view models, application startup, resources, and shell composition
- `Product.Core`: domain rules, application use cases, contracts, and models without WPF dependencies
- `Product.Infrastructure`: persistence, file system, network, device, operating-system, and update adapters
- `Product.Tests`: unit and integration tests

Add a separate contracts project only when multiple implementations or modules need a stable shared boundary.

### Modular product

Use feature assemblies and compile-time registration when independent teams, optional feature sets, or product editions justify the cost. Keep module contracts small and versioned. Avoid runtime assembly discovery unless modules must be deployed independently.

## Project boundaries

Use dependency direction:

```text
App -> Core
App -> Infrastructure
Infrastructure -> Core
Tests -> Core / Infrastructure / App test surfaces
```

Do not reference WPF assemblies from Core. Keep `Dispatcher`, `DependencyObject`, `Window`, `Brush`, and other presentation types in App or a presentation-specific library.

Use interfaces at these boundaries:

- persistence and transactions
- network and remote services
- clocks, file systems, and operating-system services when determinism matters
- device and industrial protocol access
- update, licensing, and security services
- navigation and dialogs when view models must be tested without windows

Do not create an interface for every concrete class.

## Application lifetime and Generic Host

Use the Generic Host for long-lived product applications that need DI, configuration, logging, or hosted services.

Recommended lifecycle:

1. Remove `StartupUri` from `App.xaml`.
2. Build `HostApplicationBuilder` during startup.
3. Register configuration, logging, services, view models, and windows.
4. Build and start the host.
5. Resolve and show the shell window.
6. Request cancellation during shutdown.
7. Stop and dispose the host.

Keep startup handlers thin. Move initialization into services that expose explicit progress, cancellation, and failure results.

Do not block startup indefinitely on remote services. Start in a degraded or offline mode when the product requirements allow it.

## Service lifetimes

- Use singleton for stateless, thread-safe shared services and application-wide coordinators.
- Use transient for lightweight view models or operations created per request.
- Use scoped lifetime only when the application has an explicit unit-of-work, document, session, or navigation scope.
- Do not inject scoped services into singletons directly.
- Dispose subscriptions, timers, streams, database contexts, and unmanaged handles at the lifecycle boundary that owns them.

## MVVM and UI composition

Use MVVM to separate state and behavior from views, not to eliminate all code-behind.

Acceptable code-behind includes:

- view-only animation and focus behavior
- control-specific event adaptation
- accessibility behavior tightly coupled to a control
- wiring that cannot be expressed cleanly through commands or behaviors

Keep these out of code-behind:

- business rules
- database and network operations
- device commands
- transaction orchestration
- global navigation decisions

Use `CommunityToolkit.Mvvm` when external packages are allowed and its source generators reduce boilerplate. Otherwise implement `INotifyPropertyChanged` and commands with a small internal base library. Verify the current stable package version instead of copying a stale version.

## Navigation and dialogs

Choose navigation by application shape:

- Replace the shell content for simple applications.
- Use a region or route service for multi-feature products.
- Use document or workspace navigation for multi-document applications.
- Use modal windows only for short, bounded decisions.

Represent navigation requests with typed destinations and parameters. Do not pass raw view types through Core.

Wrap user decisions behind an interface when view models need automated tests. Keep the actual `Window` and owner assignment in App.

## Concurrency and dispatcher rules

- Keep CPU-heavy work and blocking I/O off the dispatcher thread.
- Await asynchronous APIs instead of calling `.Result`, `.Wait()`, or `GetAwaiter().GetResult()` on the UI thread.
- Marshal only the final UI state mutation to the dispatcher.
- Use `CancellationToken` for user-cancellable work and shutdown.
- Use bounded channels or queues for high-frequency events.
- Coalesce telemetry and device updates before binding them to the UI.
- Avoid updating observable collections from background threads.
- Do not use `Task.Run` to hide an inherently asynchronous API or a thread-affine COM/device requirement.

For periodic work, prefer an asynchronous loop with cancellation over overlapping timer callbacks.

## Modules and extensibility

Prefer compile-time module registration:

```text
IModule.RegisterServices(IServiceCollection services)
IModule.InitializeAsync(CancellationToken token)
```

Keep initialization idempotent. Record module failures without leaving partially registered state.

Use runtime plugins only when independent delivery is required. Then define:

- compatibility and version rules
- signature and trust policy
- isolation boundaries
- dependency resolution
- update and rollback behavior
- failure containment

Do not load arbitrary assemblies from writable directories.

## Data, devices, and external systems

Keep protocols and vendor SDKs behind adapters. Translate external models into internal records at the boundary.

For device or PLC integration:

- serialize commands when the protocol requires it
- model timeouts, retries, acknowledgements, and idempotency explicitly
- separate connection state from machine state
- persist command intent when recovery requires it
- never bind vendor SDK objects directly to the UI
- never block the dispatcher on device I/O

For databases:

- define transaction boundaries in application services
- run schema migration before dependent features start
- preserve downgrade or rollback compatibility when required
- treat local cache corruption and disk-full conditions as expected operational failures

## Error handling and observability

Use structured logs with operation names, correlation identifiers, duration, result, and relevant external endpoint or device identifiers. Do not log secrets, tokens, passwords, or sensitive payloads.

Handle exceptions at the narrowest layer that can make a correct decision. At the process boundary, log and classify unhandled exceptions, but do not continue after potentially corrupting failures.

Expose user-safe messages that include an incident or correlation identifier. Keep technical detail in logs.

## Architecture review checklist

- Are WPF types absent from Core?
- Is project dependency direction acyclic?
- Is application startup owned in one place?
- Are long-running operations cancellable and observable?
- Are UI updates dispatcher-safe?
- Are service lifetimes deliberate?
- Are external systems behind adapters?
- Are retry and timeout policies bounded?
- Are fatal and recoverable failures distinguished?
- Can the application start in required offline or degraded modes?
- Are modules justified by a real deployment or ownership boundary?
- Can the product be installed, upgraded, rolled back, and diagnosed?
