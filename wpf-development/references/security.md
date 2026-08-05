# Security Engineering for WPF Products

## Contents

- Security model and trust boundaries
- Identity, authorization, and privileged actions
- Secrets and protected local storage
- Input, serialization, and file handling
- Process execution and local IPC
- Web content and embedded browsers
- Updates, packages, and code signing
- Logging, diagnostics, and privacy
- Security review checklist

## Security model and trust boundaries

Treat a desktop application as a privileged local client, not as a trusted security boundary. Document which actor can influence each input:

- signed application and update packages
- local user and administrator
- configuration files and registry values
- command-line arguments, file associations, and custom URI schemes
- local databases, caches, import files, and removable media
- remote APIs, message brokers, and update endpoints
- named pipes, sockets, COM, browser content, and plugins
- PLCs, devices, vendor SDKs, and fieldbus gateways

Do not rely on UI visibility, disabled controls, or hidden menu items as authorization. Enforce sensitive decisions in the owning application or service layer.

## Identity, authorization, and privileged actions

- Authenticate users or upstream services at the boundary that owns the protected resource.
- Authorize every privileged command, not only the screen that exposes it.
- Separate operator, maintenance, engineering, and administrative capabilities when the product requires them.
- Require explicit confirmation for destructive, irreversible, safety-relevant, or high-impact commands.
- Use short-lived elevation for privileged operating-system changes. Do not run the entire WPF process as administrator by default.
- Record who initiated a privileged action, what target was affected, and the final result.

When offline authorization is required, define credential lifetime, revocation, clock assumptions, and what happens after prolonged disconnection.

## Secrets and protected local storage

Do not store passwords, API keys, private keys, signing material, or long-lived tokens in source control, `appsettings*.json`, plain-text user settings, logs, crash dumps, or support bundles.

Use an appropriate protected mechanism, such as:

- Windows-protected credential storage for local user secrets
- certificate-backed authentication with private keys marked non-exportable where possible
- an authenticated service that keeps high-value secrets outside the desktop process
- deployment-time secret provisioning with explicit rotation and revocation

Define the scope of protection: current user, machine, service identity, or enterprise account. A machine-scoped secret may be readable by more local principals than intended.

Clear sensitive buffers where practical, avoid copying secrets into immutable strings unnecessarily, and never echo secret values in error messages.

## Input, serialization, and file handling

Treat every external file and payload as untrusted.

- Validate size, type, schema, encoding, ranges, and required fields before processing.
- Reject path traversal, alternate data streams, unexpected absolute paths, and writes outside owned directories.
- Use allow-lists for supported import formats and file extensions, but validate content independently of the extension.
- Avoid unsafe polymorphic deserialization and obsolete binary serialization.
- Bound decompression, image decoding, archive extraction, recursion, and collection sizes.
- Write durable data atomically and verify integrity before replacing the last known-good copy.
- Quarantine or preserve failed inputs when operations need forensic review, subject to privacy policy.

Do not deserialize a payload into executable types merely because it came from a local file or trusted network segment.

## Process execution and local IPC

For external processes:

- prefer direct executable and argument lists over shell command strings
- do not concatenate untrusted values into commands
- use a fixed working directory and explicit environment variables
- capture bounded output and enforce timeouts and cancellation
- validate exit codes and expected output artifacts
- avoid inheriting handles or credentials unnecessarily

For named pipes, sockets, COM, or other local IPC:

- authenticate the peer where the technology supports it
- apply the narrowest access control list
- include protocol versioning, message size limits, timeouts, and cancellation
- validate every message and command server-side
- protect against replay when commands have lasting effects
- close connections and release native resources deterministically

A local transport is not automatically trusted; another process under the same user may be able to connect.

## Web content and embedded browsers

When using WebView2 or another embedded browser:

- restrict navigation and external origins to an explicit allow-list
- do not expose broad host-object APIs to arbitrary pages
- validate every web-to-native message
- separate authentication tokens from page-accessible storage where possible
- disable or intercept downloads, new windows, permissions, and custom schemes unless required
- keep the runtime and application integration updated through a supported deployment model

Treat HTML, JavaScript, Markdown, and rich text rendered from external data as active or potentially dangerous content unless sanitized by a well-defined policy.

## Updates, packages, and code signing

- Sign installers, application binaries, update manifests, and update payloads according to the deployment model.
- Verify signature, expected product identity, version, channel, and payload hash before installation.
- Use authenticated transport, but do not treat transport security as a replacement for artifact verification.
- Prevent downgrade to vulnerable versions unless an explicit recovery policy permits it.
- Keep update logic outside the running main executable when replacement must be atomic.
- Preserve the previous working version until the new version passes a health check.
- Review dependency advisories and provenance before adding or upgrading packages.

Keep signing credentials outside source control and CI logs. Restrict release permissions and record the source commit used to produce each artifact.

## Logging, diagnostics, and privacy

Structured logs and support bundles must be useful without becoming a new data leak.

- redact credentials, tokens, authorization headers, personal data, and sensitive device payloads
- avoid logging entire configuration objects or serialized requests by default
- bound file size, retention, upload destinations, and access permissions
- separate operational identifiers from unnecessary personal information
- allow the user or operator to review support bundle contents when policy requires it
- make crash reporting opt-in or policy-controlled where appropriate

Security events should be distinguishable from ordinary operational failures, but do not expose sensitive implementation details in user-facing messages.

## Security review checklist

- Are trust boundaries and privileged commands documented?
- Is authorization enforced outside the visual layer?
- Does the process avoid unnecessary administrator rights?
- Are local and remote secrets protected, rotatable, and absent from logs?
- Are imported files and serialized payloads bounded and validated?
- Are process execution and IPC inputs free from command injection and replay risk?
- Is embedded web content restricted and message validation explicit?
- Are update artifacts signed and verified before replacement?
- Can the application roll back without accepting an unsigned or stale package?
- Are dependencies and vendor SDKs checked for supported versions and advisories?
- Are support bundles sanitized and access-controlled?
- Are security-relevant failures observable without leaking secrets?
