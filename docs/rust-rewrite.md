# Dexget native Rust rewrite

Dexget is being migrated incrementally so the existing Python release remains usable while native replacements are verified.

## Workspace

- `rust/crates/dexget-core`: platform-neutral commands, settings, reminders, and domain types.
- `rust/crates/dexget-app`: native always-on-top Dynamic Island shell.
- Future `dexget-windows`: WinRT media sessions, Core Audio, power, notifications, UI Automation, process and filesystem APIs.
- Future `dexget-automation`: deterministic routing, recorded macros, browser automation and Ollama lifecycle.
- The existing `android/` companion remains Kotlin because it is a native Android application, not part of the Windows Python runtime.

## Migration order

1. Native island shell, settings, deterministic command parser.
2. Windows media controls, volume, brightness, battery, power modes and notifications.
3. Search, file shelf, clipboard history, application launching and reminders.
4. Ollama lifecycle, natural-language routing, recorded automation and browser control.
5. Phone pairing/file transfer and remote server controls.
6. MSIX packaging, upgrade migration, parity tests, then removal of Python runtime.

## Build

```powershell
cd rust
cargo test --workspace
cargo run -p dexget
```

The Rust package uses a new executable during migration. It must not overwrite the installed Python build until the parity checklist is complete.
