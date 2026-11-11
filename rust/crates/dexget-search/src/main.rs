//! Persistent low-memory file catalog used by the Python Dynamic Island.
//!
//! Protocol: one JSON request per stdin line and one JSON response per stdout
//! line. Keeping this process alive avoids rebuilding the drive catalog for
//! every keystroke while keeping hundreds of thousands of strings out of the
//! Python heap.

use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    env, fs,
    io::{self, BufRead, BufWriter, Write},
    path::{Path, PathBuf},
    time::{Duration, SystemTime},
};

const MAX_CATALOG_ITEMS: usize = 300_000;
const MAX_RESULTS: usize = 12;
const CACHE_MAX_AGE: Duration = Duration::from_secs(60 * 60);

#[derive(Debug, Serialize, Deserialize)]
struct CatalogItem {
    path: PathBuf,
    path_folded: String,
    name: String,
    name_folded: String,
    kind: String,
}

#[derive(Debug, Deserialize)]
struct SearchRequest {
    query: String,
}

#[derive(Debug, Serialize)]
struct SearchResult<'a> {
    path: String,
    name: &'a str,
    kind: &'a str,
}

fn main() -> io::Result<()> {
    let roots = configured_roots();
    let catalog = load_cached_catalog(&roots).unwrap_or_else(|| {
        let catalog = build_catalog(&roots);
        save_catalog(&catalog);
        catalog
    });
    let stdin = io::stdin();
    let mut output = BufWriter::new(io::stdout().lock());

    for line in stdin.lock().lines() {
        let line = line?;
        let response = match serde_json::from_str::<SearchRequest>(&line) {
            Ok(request) => serde_json::to_string(&search(&catalog, &request.query))
                .unwrap_or_else(|_| "[]".to_owned()),
            Err(_) => "[]".to_owned(),
        };
        writeln!(output, "{response}")?;
        output.flush()?;
    }
    Ok(())
}

fn cache_path() -> Option<PathBuf> {
    env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|root| root.join("Dexget").join("search-catalog-v1.json"))
}

fn load_cached_catalog(roots: &[PathBuf]) -> Option<Vec<CatalogItem>> {
    let path = cache_path()?;
    let metadata = fs::metadata(&path).ok()?;
    let age = SystemTime::now()
        .duration_since(metadata.modified().ok()?)
        .ok()?;
    if age > CACHE_MAX_AGE {
        return None;
    }
    let catalog: Vec<CatalogItem> = serde_json::from_reader(fs::File::open(path).ok()?).ok()?;
    let root_prefixes: Vec<String> = roots
        .iter()
        .map(|root| root.to_string_lossy().to_lowercase())
        .collect();
    if catalog.iter().any(|item| {
        !root_prefixes
            .iter()
            .any(|root| item.path_folded.starts_with(root))
    }) {
        return None;
    }
    Some(catalog)
}

fn save_catalog(catalog: &[CatalogItem]) {
    let Some(path) = cache_path() else { return };
    let Some(parent) = path.parent() else { return };
    if fs::create_dir_all(parent).is_err() {
        return;
    }
    let temporary = path.with_extension("tmp");
    let Ok(file) = fs::File::create(&temporary) else {
        return;
    };
    if serde_json::to_writer(file, catalog).is_ok() {
        let _ = fs::rename(temporary, path);
    } else {
        let _ = fs::remove_file(temporary);
    }
}

fn configured_roots() -> Vec<PathBuf> {
    env::var("JARVIS_SEARCH_DRIVES")
        .unwrap_or_else(|_| "D:\\".to_owned())
        .split(';')
        .map(str::trim)
        .filter(|root| !root.is_empty())
        .map(PathBuf::from)
        .filter(|root| root.exists())
        .collect()
}

fn build_catalog(roots: &[PathBuf]) -> Vec<CatalogItem> {
    let ignored: HashSet<&str> = [
        "$recycle.bin",
        "system volume information",
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
    ]
    .into_iter()
    .collect();
    let mut catalog = Vec::with_capacity(16_384);
    let mut pending: Vec<PathBuf> = roots.iter().rev().cloned().collect();

    while let Some(directory) = pending.pop() {
        if catalog.len() >= MAX_CATALOG_ITEMS {
            break;
        }
        let Ok(entries) = fs::read_dir(&directory) else {
            continue;
        };
        for entry in entries.flatten() {
            if catalog.len() >= MAX_CATALOG_ITEMS {
                break;
            }
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().into_owned();
            let name_folded = name.to_lowercase();
            let Ok(file_type) = entry.file_type() else {
                continue;
            };
            if file_type.is_dir() {
                if !ignored.contains(name_folded.as_str()) {
                    pending.push(path.clone());
                }
                catalog.push(item(path, name, name_folded, "Folder"));
            } else if file_type.is_file() || file_type.is_symlink() {
                let kind = item_kind(&path);
                catalog.push(item(path, name, name_folded, kind));
            }
        }
    }
    catalog
}

fn item(path: PathBuf, name: String, name_folded: String, kind: &str) -> CatalogItem {
    let path_folded = path.to_string_lossy().to_lowercase();
    CatalogItem {
        path,
        path_folded,
        name,
        name_folded,
        kind: kind.to_owned(),
    }
}

fn item_kind(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase()
        .as_str()
    {
        "exe" => "Application",
        "lnk" => "Application",
        "mp4" | "mkv" | "mov" | "avi" | "webm" => "Video",
        "png" | "jpg" | "jpeg" | "gif" | "webp" => "Image",
        "mp3" | "wav" | "flac" | "m4a" => "Audio",
        "pdf" => "PDF file",
        _ => "File",
    }
}

fn parse_scope(query: &str) -> (Option<char>, Vec<String>, bool) {
    let mut drive = None;
    let mut terms = Vec::new();
    let mut explicit = false;
    for raw in query.split_whitespace() {
        let mut part = raw;
        if let Some(scope) = part.strip_prefix(':') {
            explicit = true;
            if scope.len() == 1 && scope.as_bytes()[0].is_ascii_alphabetic() {
                drive = scope.chars().next().map(|value| value.to_ascii_lowercase());
                continue;
            }
            part = scope;
        }
        if part.len() == 2 && part.ends_with(':') {
            explicit = true;
            drive = part.chars().next().map(|value| value.to_ascii_lowercase());
            continue;
        }
        if let Some((remainder, suffix)) = part.rsplit_once(':')
            && suffix.len() == 1
            && suffix.as_bytes()[0].is_ascii_alphabetic()
        {
            explicit = true;
            drive = suffix
                .chars()
                .next()
                .map(|value| value.to_ascii_lowercase());
            if !remainder.is_empty() {
                terms.push(remainder.to_lowercase());
            }
            continue;
        }
        if !part.is_empty() {
            terms.push(part.to_lowercase());
        }
    }
    terms.truncate(5);
    (drive, terms, explicit)
}

fn search<'a>(catalog: &'a [CatalogItem], query: &str) -> Vec<SearchResult<'a>> {
    let (drive, terms, explicit) = parse_scope(query);
    let exact_target = explicit && terms.len() == 1;
    let drive_prefix = drive.map(|letter| format!("{letter}:\\"));
    let mut matches: Vec<&CatalogItem> = catalog
        .iter()
        .filter(|item| {
            drive_prefix
                .as_ref()
                .is_none_or(|prefix| item.path_folded.starts_with(prefix))
                && terms.iter().all(|term| item.path_folded.contains(term))
        })
        .collect();

    if exact_target {
        let exact: Vec<_> = matches
            .iter()
            .copied()
            .filter(|item| item.name_folded == terms[0])
            .collect();
        if !exact.is_empty() {
            matches = exact;
        }
    }
    let last_term = terms.last().map(String::as_str).unwrap_or_default();
    matches.sort_by_key(|item| {
        (
            !item.name_folded.starts_with(last_term),
            item.name.len(),
            &item.name_folded,
        )
    });
    matches
        .into_iter()
        .take(MAX_RESULTS)
        .map(|item| SearchResult {
            path: item.path.to_string_lossy().into_owned(),
            name: &item.name,
            kind: &item.kind,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn understands_existing_drive_syntax() {
        assert_eq!(parse_scope(":D Movies").0, Some('d'));
        assert_eq!(parse_scope("Movies:D").0, Some('d'));
        assert_eq!(parse_scope("D: Movies").1, vec!["movies"]);
    }
}
