use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventKind {
    Event,
    Task,
    Schedule,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReminderLead {
    AtTime,
    Minutes(u16),
    Hours(u16),
    Days(u16),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CalendarEvent {
    pub id: u64,
    pub title: String,
    /// Unix epoch milliseconds. Kept platform-neutral for Windows and Android.
    pub starts_at_ms: i64,
    pub kind: EventKind,
    pub reminder: ReminderLead,
    pub completed: bool,
}
