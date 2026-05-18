use std::process::exit;

use crate::flags::Flags;

pub fn run_chat(_flags: &Flags, _message: Option<String>) {
    eprintln!("Error: The chat feature requires the stream module which is not available in this build.");
    exit(1);
}