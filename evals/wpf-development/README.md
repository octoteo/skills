# WPF Development evaluation scenarios

`eval.yaml` is written as JSON-compatible YAML so it can be parsed without adding a repository dependency while remaining consumable by YAML tooling.

The scenarios cover:

- creation of compact and industrial WPF products
- Generic Host and background-operation implementation
- staged modernization from .NET Framework and code-behind-heavy designs
- binding, deadlock, and memory-growth troubleshooting
- production-readiness and .NET 10 compatibility review
- offline update and rollback design
- correct behavior when Windows execution is unavailable
- non-activation for WinUI, MAUI, Avalonia, ASP.NET Core, and WinForms-only work

Repository validation checks scenario structure and coverage. It does not execute a model or claim a skilled-versus-baseline result. Store external evaluation outputs outside the skill package and summarize accepted results in release notes before promoting the skill to `v1.0.0`.
