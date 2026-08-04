---
name: wpf-development
description: Build, modernize, review, and troubleshoot production Windows Presentation Foundation applications on .NET 10 and C# 14. Use for creating new WPF solutions, upgrading or restructuring existing WPF codebases, implementing MVVM, Generic Host, dependency injection, configuration, logging, navigation, threading, testing, packaging, deployment, accessibility, localization, reliability, and .NET 10-specific WPF changes. Do not use for WinUI, .NET MAUI, Avalonia, Windows Forms-only, web UI, or .NET Framework-only work unless the task explicitly includes a WPF interoperability or migration boundary.
---

# .NET 10 WPF Engineering

## Purpose

Produce maintainable, testable, observable, and supportable WPF applications targeting .NET 10. Handle both greenfield creation and incremental modernization without forcing unnecessary frameworks or broad rewrites.

## Operating principles

1. Inspect before designing. Prefer repository evidence over assumptions.
2. Preserve behavior before improving architecture in existing applications.
3. Choose the smallest architecture that satisfies the product's real reliability and extension needs.
4. Keep UI code on the UI layer, domain rules outside WPF types, and blocking I/O off the dispatcher thread.
5. Use official .NET and WPF capabilities first. Add third-party packages only when their value and maintenance cost are explicit.
6. Make each change buildable and reviewable. Avoid large, mixed-purpose rewrites.
7. Validate on Windows because WPF is Windows-only, even when static analysis runs elsewhere.

## Determine the task mode

Select exactly one primary mode, then load only the references needed for that mode.

- **Create**: Start a new .NET 10 WPF application or solution.
- **Modernize**: Upgrade, restructure, or stabilize an existing WPF repository.
- **Implement**: Add a focused feature such as navigation, theming, DI, logging, background work, localization, or packaging.
- **Review**: Assess architecture, code quality, runtime reliability, performance, accessibility, or deployment readiness.
- **Troubleshoot**: Diagnose a build, XAML, binding, dispatcher, startup, shutdown, packaging, or runtime failure.

## Inputs and discovery

When a repository is available, discover these inputs directly instead of asking the user to repeat them:

- solution and project files (`.sln`, `.slnx`, `.csproj`)
- target frameworks, SDK pinning, central package management, and package references
- WPF and Windows Forms flags
- application startup pattern and `App.xaml`
- MVVM implementation, dependency injection, navigation, persistence, and background services
- build, test, format, publish, installer, and CI commands
- deployment targets, CPU architectures, update model, offline constraints, and rollback requirements
- existing warnings, failing tests, and operational incidents

Run the bundled inspector for an initial inventory when code access is available:

```bash
python <skill-dir>/scripts/inspect_wpf_project.py <repo-path> --format markdown
```

Use `--format json` when another tool or script will consume the result. Treat heuristic findings as prompts for inspection, not as proof of defects.

If no repository is available, state the assumptions that materially affect the design and provide a concrete implementation plan or scaffold rather than pretending files were changed.

## Reference loading guide

Load references progressively:

| Need | Reference |
|---|---|
| Project boundaries, MVVM, Generic Host, DI, navigation, threading, modules | `references/architecture.md` |
| Existing repository assessment, staged migration, behavior preservation | `references/modernization.md` |
| .NET 10 and C# 14 WPF-specific capabilities and compatibility checks | `references/dotnet10.md` |
| Unit, integration, UI, binding, accessibility, performance, and release tests | `references/testing-and-quality.md` |
| Publishing, installers, updates, rollback, configuration, logs, and recovery | `references/deployment-and-reliability.md` |
| Source freshness and official-document verification rules | `references/source-policy.md` |

## Create workflow

### 1. Establish constraints

Record the product type, expected lifetime, team size, offline requirements, device integration, data sensitivity, deployment model, supported Windows versions, CPU architectures, localization, accessibility, and update constraints.

Do not assume a complex modular platform for a small utility. Do not assume a single-project app for a long-lived industrial or enterprise product.

### 2. Choose an architecture tier

Use one of these defaults:

- **Compact**: One WPF project with feature folders and a separate test project. Use for small utilities and bounded internal tools.
- **Product**: WPF shell plus Core/Application, Infrastructure, and test projects. Use for most long-lived business or industrial applications.
- **Modular product**: Add module contracts and isolated feature assemblies only when independent ownership, optional deployment, or compile-time module boundaries are real requirements.

Document why the chosen tier is sufficient. Avoid repository, mediator, event-bus, or plugin abstractions unless a concrete use case requires them.

### 3. Scaffold safely

Use the bundled scaffold helper to preview commands:

```bash
python <skill-dir>/scripts/scaffold_wpf_solution.py <destination> --name ProductName --dry-run
```

Execute only after reviewing the destination and commands:

```bash
python <skill-dir>/scripts/scaffold_wpf_solution.py <destination> --name ProductName --execute
```

The helper requires Windows and a .NET 10 SDK for execution. It creates project boundaries but intentionally does not pin external package versions without explicit arguments.

### 4. Configure the application host

For product applications, integrate `Microsoft.Extensions.Hosting` to provide application lifetime, dependency injection, configuration, logging, and hosted services.

- Remove `StartupUri` when the host resolves and shows the main window.
- Build and start the host during application startup.
- Stop and dispose the host during application exit.
- Register windows and view models with deliberate lifetimes.
- Avoid resolving services through a global service locator.
- Keep hosted-service startup fast and cancellation-aware.

For a tiny application without configuration, logging, or background services, a host may be unnecessary. State that decision explicitly.

### 5. Implement UI and application boundaries

- Keep views declarative and binding-oriented.
- Keep view models free of `Window`, `MessageBox`, and direct dispatcher dependencies where practical.
- Put domain decisions in Core/Application services.
- Put file system, database, network, device, and operating-system access behind infrastructure interfaces.
- Marshal only UI mutations to the dispatcher; do not wrap entire I/O operations in dispatcher calls.
- Prefer cancellation, progress, timeouts, and idempotent commands for long-running operations.
- Treat design-time data, accessibility names, keyboard navigation, focus behavior, DPI scaling, theme, and localization as first-class requirements.

### 6. Add observability and recovery

- Use structured logging and correlation identifiers for user-triggered operations.
- Capture startup, shutdown, configuration, update, persistence, and external-integration failures.
- Distinguish recoverable operation failures from fatal process state.
- Provide user-safe error messages while preserving technical diagnostics in logs.
- Avoid continuing after failures that may have corrupted shared state.

### 7. Validate

Run the validation matrix in this skill and the relevant testing reference. Do not call a scaffold production-ready until it builds, starts, shuts down cleanly, and has at least one automated test around application logic.

## Modernize workflow

### 1. Establish a baseline

Before changing target frameworks or architecture:

1. Record the current SDK and target frameworks.
2. Restore and build with the repository's normal commands.
3. Run existing tests.
4. Capture current warnings and known runtime behavior.
5. Create or identify a rollback point.

Do not mix framework migration, package modernization, architecture restructuring, and UI redesign in one unreviewable step.

### 2. Inventory the repository

Run the inspector, then confirm findings manually. Identify:

- project dependency direction and cyclic references
- code-behind business logic and service-location patterns
- synchronous I/O on the UI thread
- event-handler and messenger lifetime leaks
- static mutable state
- unbounded retries or timers
- configuration and secret handling
- database migration and rollback behavior
- application startup and shutdown ownership
- packaging and update mechanisms

### 3. Migrate in controlled stages

Use the smallest safe sequence:

1. Make the existing baseline reproducible.
2. Pin or install an appropriate .NET 10 SDK.
3. Update target frameworks and restore.
4. Resolve compiler, XAML, WPF, and package compatibility issues.
5. Re-run tests and smoke tests.
6. Introduce architecture seams around the riskiest code.
7. Move features incrementally behind those seams.
8. Improve logging, cancellation, recovery, and deployment.
9. Remove obsolete compatibility code only after behavior is verified.

Read `references/modernization.md` before planning a broad restructure.

### 4. Apply .NET 10-specific checks

Always inspect the applicable items in `references/dotnet10.md`, especially:

- `net10.0-windows` and `<UseWPF>true</UseWPF>`
- empty `Grid.ColumnDefinitions` or `Grid.RowDefinitions`
- invalid `DynamicResource` usage
- WPF and Windows Forms type ambiguities
- clipboard and `BinaryFormatter`-related compatibility
- C# 14 contextual keyword and overload-resolution changes
- Fluent theme, high contrast, right-to-left layout, and resource behavior

### 5. Preserve compatibility deliberately

For each breaking behavior, choose one action and record it:

- adopt the new behavior
- add a bounded compatibility adapter
- defer with a tracked risk and removal condition
- reject the migration until a dependency is supported

Never silently suppress warnings that represent changed runtime behavior.

## Implement and troubleshoot workflow

1. Reproduce the current behavior or failure.
2. Identify the owning layer and lifecycle.
3. Make the smallest coherent change.
4. Add or update a test that would fail without the change when practical.
5. Validate startup, shutdown, cancellation, exception flow, and UI responsiveness.
6. Report the root cause, changed files, validation, and residual risk.

For binding failures, inspect the debug output, binding source, `DataContext`, property path, converter, update trigger, and notification implementation before rewriting the view model.

For hangs, separate dispatcher deadlock, synchronous wait, lock contention, blocking I/O, and external dependency timeout. Do not recommend `Task.Run` as a universal fix.

For memory growth, inspect event subscriptions, static references, timers, collections, cached views, image sources, navigation journals, and unmanaged resource disposal.

## Architecture rules

- Prefer constructor injection.
- Prefer explicit interfaces at external or independently testable boundaries, not for every class.
- Keep singleton services stateless or concurrency-safe.
- Do not inject scoped services into singletons without an explicit scope strategy.
- Treat windows and long-lived view models as lifecycle owners; dispose subscriptions and resources.
- Use immutable messages or operation records across asynchronous boundaries.
- Keep database transactions and device commands outside view models.
- Use compile-time module registration by default. Use runtime plugins only when independent deployment is required.
- Keep update logic outside the main executable when atomic replacement or rollback requires it.

## Validation matrix

Run the repository's own commands first. Add the following where applicable:

```bash
dotnet --info
dotnet restore
dotnet build --no-restore
dotnet test --no-build
dotnet format --verify-no-changes
```

Validate on Windows:

- cold startup and clean shutdown
- main navigation and one representative end-to-end workflow
- cancellation and timeout behavior
- unhandled exception routing and log creation
- light, dark, high-contrast, and system theme behavior
- 100%, 150%, and 200% DPI where supported
- keyboard-only navigation and screen-reader names for critical controls
- supported locales, right-to-left layout when applicable, and text expansion
- offline startup and degraded external dependencies
- publish output for each supported runtime identifier
- installer install, upgrade, repair, uninstall, and rollback paths

Do not claim validation that was not run. Distinguish static review, build validation, automated tests, and manual Windows UI verification.

## Output contract

For code-changing tasks, end with:

1. **Outcome**: what now works.
2. **Architecture decision**: the chosen boundary or pattern and why.
3. **Changed files**: grouped by purpose.
4. **Validation**: exact commands and manual checks completed.
5. **Risks and follow-up**: only material unresolved items.

For review tasks, provide:

1. an executive assessment
2. evidence-backed findings ordered by severity
3. a staged remediation plan
4. validation criteria for each stage

Use concrete file paths, types, commands, and failure modes. Avoid generic advice that cannot be applied to the repository.

## Failure recovery

- If the .NET 10 SDK is unavailable, stop execution and provide the exact prerequisite rather than generating unverified build output.
- If the host operating system is not Windows, perform static analysis and command planning only; mark Windows build and UI validation as pending.
- If package compatibility is uncertain, verify the package's official documentation or NuGet metadata before changing versions.
- If the baseline already fails, separate pre-existing failures from migration failures.
- If a broad rewrite cannot be validated incrementally, reduce scope and introduce a compatibility seam first.
