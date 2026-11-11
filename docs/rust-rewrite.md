# Dexget native Rust rewrite

Dexget uses a hybrid architecture. The PyQt UI and mature Windows automation
remain in Python, while measured CPU- or memory-heavy services move to Rust.
Every native service has a Python fallback so packaging or startup failures do
not remove features.

## Workspace

- `rust/crates/dexget-core`: platform-neutral commands, settings, reminders, and domain types.
- `rust/crates/dexget-app`: native always-on-top Dynamic Island shell.
- `rust/crates/dexget-search`: persistent low-memory drive catalog used by the
  production PyQt island.
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

The native UI is an experimental shell. The production application remains the
PyQt island; Rust sidecars are adopted only when they preserve behavior and
show a measurable efficiency improvement.
