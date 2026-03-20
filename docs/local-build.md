# Local Build Script

This repo now includes a local build helper:

- [scripts/local_rustdesk_build.py](/Users/savannachow/Github/rdgen/scripts/local_rustdesk_build.py)

It does not build from this repo alone. Instead it:

1. clones a fresh local copy of `rustdesk/rustdesk`
2. applies rdgen-style customizations
3. generates the Flutter/Rust bridge
4. builds macOS and/or Android artifacts on your Mac

## Config

Start from:

- [examples/local-build-config.example.json](/Users/savannachow/Github/rdgen/examples/local-build-config.example.json)
- [examples/local-build-config.example.jsonc](/Users/savannachow/Github/rdgen/examples/local-build-config.example.jsonc)
- [examples/local-build-config.savanna.jsonc](/Users/savannachow/Github/rdgen/examples/local-build-config.savanna.jsonc)

If you want inline comments, use the `.jsonc` examples. The script accepts:

- `# comment`
- `// comment`
- `/* block comment */`

The config supports:

- branding:
  - `app_name`
  - `filename`
  - `company_name`
- server wiring:
  - `server`
  - `key`
  - `api_server`
  - `url_link`
  - `download_link`
- mobile package id:
  - `android_app_id`
- assets:
  - `assets.icon_path`
  - `assets.logo_path`
- client policy:
  - `client_config.*`
- feature toggles:
  - `features.delay_fix`
  - `features.cycle_monitor`
  - `features.x_offline`
  - `features.hide_cm`
  - `features.remove_new_version_notif`
- platform-specific build settings:
  - `macos.*`
  - `android.*`

## Requirements

Host:

- macOS
- Xcode + command line tools
- Flutter on `PATH`
- Rust + `cargo` + `rustup`
- `git`
- `cmake`
- `ninja`
- `pkg-config`
- `clang`

For icon customization:

- `imagemagick`
- `potrace`
- `iconutil`

For Android:

- Java 17
- Android SDK
- Android NDK `r27c` or compatible install path wired through `toolchain.android_ndk`

Useful install line for Homebrew-managed pieces:

```bash
brew install imagemagick potrace cmake ninja pkg-config
```

## Usage

```bash
python3 scripts/local_rustdesk_build.py --config examples/local-build-config.example.jsonc
```

Outputs:

- fresh build workspace under `build/workspaces/...`
- artifacts under `dist/...`
- summary file under `dist/.../build-summary.json`

## Notes

- macOS build currently targets the host Mac architecture.
- Android build can emit one or more APKs via `android.abis`.
- If Android signing fields are empty, the script falls back to debug signing.
- `privacy_path` is accepted in config, but not yet wired into macOS/Android local builds.
- API server is a build-time parameter here, but Pro / Address Book account credentials are still runtime login data.
- Flutter SDK patching is opt-in via:
  - `toolchain.patch_flutter_sdk`
  - `toolchain.flutter_scheduler_workaround`
