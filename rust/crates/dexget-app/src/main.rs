#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use dexget_core::{Command, CommandParser};
use eframe::egui::{self, Color32, CornerRadius, Frame, Margin, RichText, Stroke, ViewportBuilder};

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: ViewportBuilder::default()
            .with_title("Dexget Native")
            .with_inner_size([390.0, 54.0])
            .with_min_inner_size([290.0, 54.0])
            .with_decorations(false)
            .with_transparent(true)
            .with_always_on_top(),
        ..Default::default()
    };
    eframe::run_native(
        "Dexget Native",
        options,
        Box::new(|context| {
            context.egui_ctx.set_visuals(egui::Visuals::dark());
            Ok(Box::<DexgetApp>::default())
        }),
    )
}

#[derive(Default)]
struct DexgetApp {
    expanded: bool,
    query: String,
    status: String,
    parser: CommandParser,
}

impl DexgetApp {
    fn execute(&mut self) {
        self.status = match self.parser.parse(&self.query) {
            Command::PlayPause => "Media play/pause".into(),
            Command::NextTrack => "Next track".into(),
            Command::PreviousTrack => "Previous track".into(),
            Command::SetVolume(value) => format!("Volume {value}%"),
            Command::OpenPath(path) => format!("Open {}", path.display()),
            Command::Search { scope, query } => format!(
                "Search {} in {}",
                query,
                scope
                    .map(|path| path.display().to_string())
                    .unwrap_or("indexed files".into())
            ),
            Command::AskLocalModel(prompt) => format!("Ask local model: {prompt}"),
        };
    }
}

impl eframe::App for DexgetApp {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        let target_height = if self.expanded { 190.0 } else { 54.0 };
        context.send_viewport_cmd(egui::ViewportCommand::InnerSize(
            [390.0, target_height].into(),
        ));

        egui::CentralPanel::default()
            .frame(
                Frame::new()
                    .fill(Color32::from_rgb(9, 11, 14))
                    .stroke(Stroke::new(1.0_f32, Color32::from_rgb(55, 59, 66)))
                    .corner_radius(CornerRadius::same(27))
                    .inner_margin(Margin::symmetric(18, 9)),
            )
            .show(context, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new("DEXGET").strong().color(Color32::WHITE));
                    ui.add_space(8.0);
                    ui.label(
                        RichText::new(if self.expanded { "Command" } else { "Ready" })
                            .color(Color32::GRAY),
                    );
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if ui.button(if self.expanded { "−" } else { "+" }).clicked() {
                            self.expanded = !self.expanded;
                        }
                    });
                });

                if self.expanded {
                    ui.add_space(12.0);
                    let response = ui.add_sized(
                        [ui.available_width(), 34.0],
                        egui::TextEdit::singleline(&mut self.query)
                            .hint_text("Search, control Windows, or ask Dexget"),
                    );
                    if response.lost_focus()
                        && ui.input(|input| input.key_pressed(egui::Key::Enter))
                    {
                        self.execute();
                    }
                    ui.add_space(8.0);
                    ui.horizontal(|ui| {
                        if ui.button("Run").clicked() {
                            self.execute();
                        }
                        ui.label(
                            RichText::new(&self.status)
                                .small()
                                .color(Color32::LIGHT_GRAY),
                        );
                    });
                }
            });
    }
}
