//! Platform-neutral domain model for the native Dexget rewrite.

pub mod command;
pub mod event;
pub mod settings;

pub use command::{Command, CommandParser};
pub use event::{CalendarEvent, EventKind, ReminderLead};
pub use settings::{AppSettings, SettingsStore};
