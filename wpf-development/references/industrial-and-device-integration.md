# Industrial and Device Integration for WPF

## Contents

- Scope and safety boundary
- Device abstraction and ownership
- Command lifecycle and idempotency
- State, freshness, and reconciliation
- Connectivity, retry, and backpressure
- Recipes, configuration, and offline operation
- Auditability and operator experience
- Simulation and validation
- Industrial readiness checklist

## Scope and safety boundary

A WPF HMI, supervisory client, or production application must not silently become the functional-safety controller. Keep emergency stop, safe torque off, interlocks, guarded motion, and other safety functions in the certified safety architecture and device layer appropriate to the machine.

Document explicitly:

- which decisions are informational, supervisory, operational, or safety-related
- which controller owns the authoritative machine state
- what the WPF application may command
- which commands require physical conditions, authorization, or confirmation
- what happens when the application, network, database, or device is unavailable

Never infer that a command succeeded because a button was pressed or a request was transmitted.

## Device abstraction and ownership

Keep protocol libraries and vendor SDK types out of views and business rules.

Use explicit boundaries for:

- connection and session lifecycle
- typed reads and writes
- command submission and acknowledgment
- subscriptions or polling
- diagnostics and quality indicators
- clock and timestamp handling
- simulator and real-device implementations

One service should clearly own each device connection. Avoid multiple view models opening independent sessions to the same PLC, robot, scanner, camera, or gateway unless the protocol and product design explicitly support it.

Long-lived device services must be concurrency-safe, cancellation-aware, and disposable. Do not block the dispatcher while waiting for I/O.

## Command lifecycle and idempotency

Model an industrial command as a lifecycle, not a Boolean write:

1. validate local preconditions
2. assign a correlation or command identifier
3. submit the request
4. receive transport acknowledgment
5. observe controller acceptance or rejection
6. observe completion, timeout, cancellation, or fault
7. reconcile final machine state
8. persist the audit result where required

Distinguish transport success from process completion.

For commands that may be retried after timeout or reconnect, define an idempotency strategy. Examples include controller sequence numbers, command IDs, monotonic counters, or explicit query-before-retry behavior. Blindly repeating motion, dosing, printing, or material-transfer commands can duplicate physical effects.

## State, freshness, and reconciliation

Every displayed value should have an understood source, timestamp, quality, and freshness policy.

- Mark stale, simulated, estimated, or unavailable data visibly.
- Do not present the last received value as live after the connection is lost.
- Separate desired state, commanded state, controller state, and confirmed physical state.
- Reconcile state after reconnect before enabling commands.
- Define how conflicting server, controller, and cached values are resolved.
- Use monotonic sequence numbers or timestamps where ordering matters.

After restart, reconcile in-flight work from durable records and authoritative controller state. Do not assume an operation failed merely because the client did not receive its completion message.

## Connectivity, retry, and backpressure

Use bounded connection and retry behavior:

- explicit connect and operation timeouts
- cancellation on shutdown or mode change
- exponential or policy-based retry with an upper bound
- jitter when many clients reconnect to a shared service
- circuit breaking or degraded mode for persistent failures
- a maximum queue size and a clear overflow policy

Do not queue safety-relevant or time-sensitive commands indefinitely. Some operations should be rejected when offline rather than replayed later.

For high-rate telemetry, decouple acquisition from rendering. Coalesce UI updates, sample or aggregate values, and bound memory. The dispatcher should receive only the state needed for the current visual frame, not every raw device event.

## Recipes, configuration, and offline operation

Treat recipes, product parameters, calibration data, and machine configuration as versioned operational data.

Define:

- schema version and migration behavior
- units, ranges, precision, and locale-independent serialization
- approval and authorization rules
- compatibility with controller and software versions
- checksum or signature requirements where tampering matters
- activation time and rollback behavior
- offline editing and synchronization conflict rules

Validate a recipe before transmission and verify what the controller accepted. Preserve the previous known-good version until the new configuration is confirmed.

## Auditability and operator experience

For consequential actions, record:

- operator or service identity
- command and target
- requested parameters with sensitive fields redacted
- local validation result
- controller acknowledgment and final result
- timestamps and correlation identifiers
- software, recipe, and controller versions when relevant

The UI should make state and authority clear:

- connected, reconnecting, offline, simulated, or degraded
- automatic, manual, maintenance, or locked mode
- command pending, accepted, running, completed, rejected, timed out, or unknown
- stale-data age and quality
- reason a command is unavailable

Avoid modal-message storms during repeated device faults. Aggregate recurring alarms while preserving first occurrence, latest occurrence, count, and acknowledgment state.

## Simulation and validation

Provide a simulator or protocol test double for deterministic development, but make simulation unmistakable in the UI and logs.

Use multiple validation levels:

- unit tests for command state machines, ranges, retries, and reconciliation
- protocol contract tests against recorded or synthetic frames
- simulator integration tests for reconnect and fault scenarios
- hardware-in-the-loop tests for vendor SDK and timing behavior
- machine acceptance tests with controlled physical conditions

Test at least:

- startup with every external dependency unavailable
- connection loss during read, write, and long-running command
- duplicate, delayed, out-of-order, and malformed messages
- controller restart and client restart
- stale telemetry and clock differences
- full queues and slow consumers
- power loss during recipe or update activation
- recovery from partial completion

Do not claim physical behavior, cycle time, or safety validation from simulator-only evidence.

## Industrial readiness checklist

- Is the safety boundary explicit and outside the WPF client where required?
- Does one clear owner manage each device session?
- Are transport acknowledgment and physical completion modeled separately?
- Can every retry avoid duplicate physical effects?
- Are freshness, quality, and simulated state visible?
- Does reconnect reconcile authoritative state before enabling commands?
- Are retries, queues, polling, and UI updates bounded?
- Are recipes versioned, validated, auditable, and reversible?
- Can the application start and shut down safely with devices unavailable?
- Are operator actions and controller outcomes correlated end to end?
- Are simulation, hardware-in-the-loop, and machine tests clearly distinguished?
- Are unknown or partially completed operations surfaced instead of guessed?
