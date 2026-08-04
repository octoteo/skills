# Testing and Quality for WPF Applications

## Contents

- Test pyramid
- Core and view-model tests
- Integration tests
- UI and smoke tests
- Binding and XAML validation
- Accessibility and localization
- Performance and reliability
- Continuous integration
- Release evidence

## Test pyramid

Use the lowest-cost test that proves the behavior:

1. unit tests for domain and application logic
2. view-model tests for commands, state transitions, validation, and cancellation
3. integration tests for persistence, configuration, external adapters, and serialization
4. focused Windows UI automation for critical user journeys
5. manual exploratory tests for visual, accessibility, installation, and hardware scenarios

Do not rely solely on UI automation. It is slower and more fragile than testing logic below the view.

## Core and view-model tests

Test:

- state transitions and command availability
- validation and error mapping
- cancellation and retry decisions
- progress reporting
- duplicate command suppression
- navigation requests
- property-change notifications when they are behaviorally important
- disposal of subscriptions and cancellation sources

Use deterministic clocks, schedulers, file systems, and external adapters where timing or environment affects behavior.

Avoid tests that assert implementation details such as private method call order unless the ordering is the requirement.

## Integration tests

Exercise real boundaries in isolated environments:

- database schema creation and migration
- transaction rollback
- configuration binding and validation
- JSON and file format compatibility
- local IPC or service contracts
- device protocol framing with simulators
- update manifest parsing and signature validation

Keep test data versioned. Include malformed, partial, old-version, and oversized inputs.

## UI and smoke tests

At minimum, automate or manually verify:

- application launch
- shell display
- one critical navigation path
- one data-entry or command workflow
- cancellation or failure feedback
- clean shutdown

For UI automation, assign stable automation identifiers and accessible names. Avoid selectors based only on visual tree position or localized text.

Run UI tests in a controlled Windows session with known DPI and theme. Separate environmental failures from product failures.

## Binding and XAML validation

Treat binding errors as quality defects. During development and tests:

- inspect binding trace output
- verify `DataContext` ownership
- validate converter behavior and culture
- verify `UpdateSourceTrigger`
- confirm notification paths for nested properties
- check resource dictionary load order and key collisions
- instantiate representative views to catch XAML parse failures

Consider a debug-time policy that promotes binding errors to test failures for critical views.

## Accessibility and localization

Verify critical workflows with:

- keyboard only
- visible focus
- screen-reader names and roles
- high contrast
- text scaling
- 100%, 150%, and 200% DPI
- long translated strings
- missing resource fallback
- right-to-left layout where applicable

Do not treat automated accessibility scans as complete. Include a manual keyboard and screen-reader pass for release-critical flows.

## Performance and reliability

Measure before optimizing. Capture:

- cold and warm startup
- first navigation or first data load
- dispatcher stalls
- memory after repeated navigation
- allocation and collection pressure during high-frequency updates
- external call latency and timeout behavior
- shutdown duration

Use traces and dumps appropriate to the failure. Avoid speculative caching that creates stale state or memory leaks.

Run soak tests for products that maintain long device or network sessions. Include reconnect, sleep/resume, network loss, clock change, and disk pressure when relevant.

## Continuous integration

CI should run static and non-UI tests on every change. Use a Windows runner for WPF build and tests.

Recommended checks:

```bash
dotnet restore
dotnet build --no-restore
dotnet test --no-build
dotnet format --verify-no-changes
```

Add package vulnerability audit, signed artifact verification, and installer tests when the product risk warrants them.

Do not hide warnings globally. Establish a warning baseline and reduce it deliberately.

## Release evidence

A release record should include:

- source revision
- SDK and dependency lock information
- build and test results
- supported Windows versions and runtime identifiers
- installer and package hashes
- code-signing status
- database migration and rollback test result
- update and rollback test result
- known issues and operational workarounds

Distinguish tests that ran automatically from manual checks and tests blocked by unavailable hardware.
