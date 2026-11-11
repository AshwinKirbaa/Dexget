use serde::{Deserialize, Serialize};
use std::{
    fs,
    path::{Path, PathBuf},
};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct AppSettings {
    pub ollama_model: String,
    pub island_always_on_top: bool,
    pub close_model_after_task: bool,
    pub default_search_roots: Vec<PathBuf>,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            ollama_model: "gemma3:4b".into(),
            island_always_on_top: true,
            close_model_after_task: true,
            default_search_roots: vec![PathBuf::from("C:\\"), PathBuf::from("D:\\")],
        }
    }
}

#[derive(Debug, Error)]
pub enum SettingsError {
    #[error("failed to read settings: {0}")]
    Read(#[source] std::io::Error),
    #[error("settings contain invalid JSON: {0}")]
    Parse(#[source] serde_json::Error),
    #[error("failed to write settings: {0}")]
    Write(#[source] std::io::Error),
}

pub struct SettingsStore {
    path: PathBuf,
}

impl SettingsStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }
    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn load(&self) -> Result<AppSettings, SettingsError> {
        if !self.path.exists() {
            return Ok(AppSettings::default());
        }
        let data = fs::read_to_string(&self.path).map_err(SettingsError::Read)?;
        serde_json::from_str(&data).map_err(SettingsError::Parse)
    }

    pub fn save(&self, settings: &AppSettings) -> Result<(), SettingsError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent).map_err(SettingsError::Write)?;
        }
        let data = serde_json::to_vec_pretty(settings).expect("serializing settings cannot fail");
        let temporary = self.path.with_extension("tmp");
        fs::write(&temporary, data).map_err(SettingsError::Write)?;
        fs::rename(temporary, &self.path).map_err(SettingsError::Write)
    }
}
