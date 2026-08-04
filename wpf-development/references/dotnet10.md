# .NET 10 and WPF Compatibility Guide

## Contents

- Target framework baseline
- WPF changes in .NET 10
- Migration hazards
- C# 14 considerations
- Generic Host integration
- Theme, accessibility, and localization
- Clipboard and serialization
- Verification checklist

## Target framework baseline

Use a Windows target framework and enable WPF:

```xml
<PropertyGroup>
  <OutputType>WinExe</OutputType>
  <TargetFramework>net10.0-windows</TargetFramework>
  <UseWPF>true</UseWPF>
  <Nullable>enable</Nullable>
  <ImplicitUsings>enable</ImplicitUsings>
</PropertyGroup>
```

Use a more specific Windows target platform only when an API requires it and the minimum supported Windows version is intentional.

Pin the SDK with `global.json` when reproducible local and CI builds require it. Keep the roll-forward policy explicit.

## WPF changes in .NET 10

.NET 10 WPF includes performance work in UI automation, file dialogs, pixel conversion, font loading, dynamic resources, input, tracing, regular expressions, and XAML parsing. Treat these as runtime improvements, not permission to remove application-level performance measurement.

Fluent styling support includes additional controls and fixes. Verify every control used by the product, including focus, validation, high contrast, right-to-left layout, and disabled states. Fluent support is not a substitute for a complete design system.

WPF and Windows Forms use aligned clipboard APIs in .NET 10. Some older clipboard methods related to `BinaryFormatter` compatibility are obsolete. Prefer safe, explicit formats and JSON or domain-specific serialization for application-owned data.

.NET 10 adds more `MessageBox` button and result combinations and supports compact string syntax for Grid row and column definitions. Use new APIs only when they improve clarity and do not reduce compatibility with required controls or tooling.

## Migration hazards

### Empty Grid definition collections

Remove empty elements:

```xml
<Grid.ColumnDefinitions />
<Grid.RowDefinitions />
```

Only declare the collections when they contain definitions.

### Invalid DynamicResource usage

Audit `DynamicResource` references. Confirm that:

- the key exists in every required theme or merged dictionary
- the target is a dependency property that supports a dynamic resource
- resource dictionaries load before dependent views
- theme replacement does not leave stale or missing keys

Invalid usage that was previously ignored can now fail at runtime.

### WPF and Windows Forms type ambiguity

Projects referencing both UI stacks may need fully qualified names for types such as `MenuItem` and `ContextMenu`. Prefer aliases at the interop boundary instead of spreading fully qualified names throughout the codebase.

### WPF and WinForms interoperability

Keep interop localized. Verify DPI behavior, keyboard focus, message loops, ownership, disposal, and airspace limitations for `WindowsFormsHost` or `ElementHost` scenarios.

## C# 14 considerations

Review code that uses identifiers now treated contextually, especially `field` inside property accessors and `extension` in declarations. Rename or escape only when required; do not perform broad cosmetic renames without evidence.

Review overload resolution involving arrays, spans, and LINQ where compiler binding may select a different method. Use explicit casts or static method calls when semantics must be unambiguous.

Enable nullable reference types deliberately. Avoid turning on nullable annotations for an entire legacy solution without a staged warning strategy.

## Generic Host integration

WPF does not add Generic Host automatically. For product applications:

- remove `StartupUri`
- create the builder during application startup
- register services, windows, and hosted services
- start the host before showing the shell
- stop and dispose it during exit
- copy `appsettings.json` to the output directory when using file configuration

Use the current stable `Microsoft.Extensions.Hosting` 10.0.x package version. Verify the version from official package metadata rather than hardcoding a version from this reference.

## Theme, accessibility, and localization

Verify:

- system, light, dark, and high-contrast themes
- Windows accent behavior when used
- keyboard navigation, focus visuals, access keys, and automation names
- text scaling and DPI scaling
- right-to-left layout when supported
- localized resource fallback and text expansion
- control templates under validation, disabled, hover, pressed, and error states

Do not encode status only with color. Keep contrast and focus visibility measurable.

## Clipboard and serialization

Treat clipboard data as untrusted input. Validate size and format before deserialization. Do not use `BinaryFormatter` or unsafe type-directed deserialization.

Prefer:

- plain text for human-readable exchange
- explicit image or file-drop formats
- JSON with a fixed schema for application-owned structured data
- a versioned custom format when backward compatibility is required

Handle clipboard contention and unavailable clipboard operations without crashing the application.

## Verification checklist

- Does every WPF project target `net10.0-windows` or an intentional Windows-specific variant?
- Is `<UseWPF>true</UseWPF>` present?
- Are empty Grid definition collections removed?
- Are dynamic resource keys valid across themes?
- Are WPF and WinForms ambiguities resolved at the boundary?
- Are obsolete clipboard APIs removed or isolated?
- Are C# 14 keyword and overload changes reviewed?
- Does the application start and stop the Generic Host cleanly?
- Are Fluent, high-contrast, DPI, keyboard, and localization behaviors verified?
- Are package versions verified against current official metadata?
