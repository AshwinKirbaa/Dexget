use std::path::PathBuf;

/// Commands understood without loading an LLM. More complex text is passed to
/// the local model only after this deterministic fast path has declined it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    OpenPath(PathBuf),
    Search {
        scope: Option<PathBuf>,
        query: String,
    },
    SetVolume(u8),
    PlayPause,
    NextTrack,
    PreviousTrack,
    AskLocalModel(String),
}

#[derive(Debug, Default)]
pub struct CommandParser;

impl CommandParser {
    pub fn parse(&self, input: &str) -> Command {
        let text = input.trim();
        let lower = text.to_ascii_lowercase();

        if matches!(
            lower.as_str(),
            "play" | "pause" | "play pause" | "play/pause"
        ) {
            return Command::PlayPause;
        }
        if matches!(lower.as_str(), "next" | "next track" | "skip") {
            return Command::NextTrack;
        }
        if matches!(lower.as_str(), "previous" | "previous track" | "go back") {
            return Command::PreviousTrack;
        }
        if let Some(value) = lower.strip_prefix("volume ")
            && let Ok(value) = value.trim_end_matches('%').parse::<u8>()
        {
            return Command::SetVolume(value.min(100));
        }
        if let Some(path) = text.strip_prefix("open ") {
            return Command::OpenPath(PathBuf::from(path.trim_matches('"')));
        }

        // Preserve Dexget's existing drive-scoped search syntax, for example
        // `:D Movies` and `Movies:D`.
        if let Some(rest) = text.strip_prefix(':') {
            let mut pieces = rest.splitn(2, char::is_whitespace);
            if let Some(drive) = pieces.next().filter(|part| part.len() == 1) {
                return Command::Search {
                    scope: Some(PathBuf::from(format!("{}:\\", drive.to_ascii_uppercase()))),
                    query: pieces.next().unwrap_or_default().trim().to_owned(),
                };
            }
        }
        if let Some((query, drive)) = text.rsplit_once(':')
            && drive.len() == 1
            && drive
                .chars()
                .all(|character| character.is_ascii_alphabetic())
        {
            return Command::Search {
                scope: Some(PathBuf::from(format!("{}:\\", drive.to_ascii_uppercase()))),
                query: query.trim().to_owned(),
            };
        }

        Command::AskLocalModel(text.to_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_drive_scoped_search_in_both_supported_forms() {
        let parser = CommandParser;
        assert_eq!(
            parser.parse(":D Movies"),
            Command::Search {
                scope: Some(PathBuf::from("D:\\")),
                query: "Movies".into()
            }
        );
        assert_eq!(
            parser.parse("Movies:D"),
            Command::Search {
                scope: Some(PathBuf::from("D:\\")),
                query: "Movies".into()
            }
        );
    }

    #[test]
    fn caps_volume_at_one_hundred() {
        assert_eq!(CommandParser.parse("volume 140"), Command::SetVolume(100));
    }
}
