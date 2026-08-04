# Source and Freshness Policy

## Purpose

Keep recommendations aligned with supported .NET 10 and WPF behavior while avoiding stale package versions and preview-only guidance.

## Source priority

Use sources in this order:

1. Microsoft Learn documentation for .NET, WPF, C# language, deployment, and Generic Host behavior.
2. Official `dotnet`, `dotnet/wpf`, and relevant Microsoft-owned GitHub repositories for release notes and implementation details.
3. Official NuGet package metadata and package release notes.
4. Maintainer documentation for third-party packages.
5. Community sources only for reproducible troubleshooting evidence, never as the sole authority for compatibility or security claims.

## Freshness rules

- Verify the installed SDK with `dotnet --info` and `dotnet --list-sdks`.
- Treat package versions as dynamic. Do not select them from memory.
- Prefer stable .NET 10-compatible releases unless the user explicitly requests previews.
- Check release notes before changing WPF theme libraries, database providers, installers, update frameworks, or vendor SDKs.
- Check published security advisories before adding or retaining packages.
- Record the verification date when producing a long-lived migration or architecture document.

## Baseline official references

- WPF changes in .NET 10: `https://learn.microsoft.com/dotnet/desktop/wpf/whats-new/net100`
- Generic Host in WPF: `https://learn.microsoft.com/dotnet/desktop/wpf/app-development/how-to-use-host-builder`
- .NET Generic Host: `https://learn.microsoft.com/dotnet/core/extensions/generic-host`
- .NET dependency injection: `https://learn.microsoft.com/dotnet/core/extensions/dependency-injection/usage`
- .NET 10 overview: `https://learn.microsoft.com/dotnet/core/whats-new/dotnet-10/overview`
- WPF repository: `https://github.com/dotnet/wpf`
- .NET skills repository: `https://github.com/dotnet/skills`

## Evidence rules

When changing code, cite evidence in the work summary through file paths, build output, tests, traces, or official documentation. Label inferences as inferences.

Do not claim a package, Windows version, installer technology, or vendor SDK is supported without verification.
