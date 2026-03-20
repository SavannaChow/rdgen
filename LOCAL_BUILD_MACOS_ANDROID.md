# Local Build Audit: RustDesk macOS + Android

## Verdict

This repository is **not** a standalone RustDesk app source tree.

It is a **generator/orchestrator** that:

- collects customization options with Django
- dispatches GitHub Actions workflows
- downloads `rustdesk/rustdesk` during the workflow
- applies patches/customizations on top of upstream RustDesk

So:

- `rdgen` **can drive** macOS and Android builds
- `rdgen` **does not fully include** everything needed to build the apps by itself
- for local builds, you still need the upstream RustDesk source tree and platform toolchains

## Evidence In This Repo

- The UI exposes `android` and `macos` as build targets in [rdgenerator/forms.py](/Users/savannachow/Github/rdgen/rdgenerator/forms.py#L7).
- The backend dispatches dedicated workflows:
  - [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml)
  - [generator-macos.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-macos.yml)
- Both workflows explicitly check out upstream RustDesk instead of using this repo as the app source:
  - [generator-macos.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-macos.yml#L109)
  - [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L176)
- The shared bridge workflow also checks out upstream RustDesk:
  - [bridge.yml](/Users/savannachow/Github/rdgen/.github/workflows/bridge.yml#L21)

## What This Repo Already Contains

- Django generator server
- GitHub Actions workflows for:
  - Windows
  - Linux
  - Android
  - macOS
- Custom patches under [.github/patches](/Users/savannachow/Github/rdgen/.github/patches)
- Logic for injecting:
  - server
  - public key
  - app name
  - icon/logo/privacy image
  - Android app id
  - advanced RustDesk settings

## What Is Missing For A Real Local Build

### 1. Upstream RustDesk source

This repo does not include the actual RustDesk app source.

You still need:

```bash
git clone --recursive https://github.com/rustdesk/rustdesk.git
```

If you want the exact versions exposed by this generator UI, they are currently capped at `1.4.6` or `master` in [rdgenerator/forms.py](/Users/savannachow/Github/rdgen/rdgenerator/forms.py#L8).

Current upstream tags fetched on 2026-03-19 still show `1.4.6` as the latest numbered tag, plus `nightly`.

### 2. Platform toolchains

The workflows assume external platform tooling that is not vendored here.

For macOS, the workflow expects:

- Xcode / Apple SDKs
- Homebrew packages:
  - `imagemagick`
  - `potrace`
  - `nasm`
  - `cmake`
  - `gcc`
  - `wget`
  - `ninja`
  - `llvm`
  - `create-dmg`
  - `pkg-config`
- Rust toolchains:
  - `1.81` for the macOS build
  - bridge flow still references `1.75`
- Flutter `3.24.5`
- `vcpkg`

Source:

- [generator-macos.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-macos.yml#L17)
- [generator-macos.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-macos.yml#L124)
- [generator-macos.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-macos.yml#L220)
- [bridge.yml](/Users/savannachow/Github/rdgen/.github/workflows/bridge.yml#L11)

For Android, the workflow expects:

- Java 17
- Android SDK
- Android NDK `r27c`
- Flutter `3.24.5`
- Rust `1.75`
- `cargo-ndk` `3.1.2`
- `vcpkg`
- Rust Android targets:
  - `aarch64-linux-android`
  - `armv7-linux-androideabi`
  - `x86_64-linux-android`

Source:

- [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L18)
- [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L134)
- [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L204)
- [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L251)

### 3. Secrets and signing material

This repo expects external secrets, not checked in:

- `ANDROID_SIGNING_KEY`
- `ANDROID_ALIAS`
- `ANDROID_KEY_STORE_PASSWORD`
- `ANDROID_KEY_PASSWORD`
- `MACOS_P12_BASE64`
- `MACOS_P12_PASSWORD`
- `ZIP_PASSWORD`
- `GENURL`

Source:

- [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L36)
- [generator-macos.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-macos.yml#L36)
- [.github/actions/decrypt-secrets/action.yml](/Users/savannachow/Github/rdgen/.github/actions/decrypt-secrets/action.yml)

Unsigned builds are still possible, but:

- unsigned macOS apps will hit Gatekeeper/notarization friction
- Android release signing will fall back to debug signing in this workflow logic

### 4. The build runs against a second workspace, not this repo

The workflow edits files inside upstream RustDesk paths such as:

- `flutter/macos/Runner/Info.plist`
- `flutter/android/app/build.gradle`
- `libs/hbb_common/src/config.rs`
- `src/common.rs`
- `build.py`

That means the real local-build workspace must be the cloned `rustdesk/rustdesk` repo, with patches/instructions borrowed from this repo.

## Resource Gaps You Need To Fill Locally

If your goal is "build on my own Mac", the missing pieces to collect are:

1. Upstream RustDesk source tree with submodules.
2. A reproducible local patch/apply process that ports rdgen customizations into that tree.
3. macOS code-signing assets if you want a clean distributable `.app` / `.dmg`.
4. Android keystore if you want proper release APK signing.
5. A local build script, because this repo only defines the process inside GitHub Actions YAML.

## Recommended Local Workspace Layout

Use two sibling directories:

```text
~/Github/rdgen
~/Github/rustdesk
```

Then treat `rdgen` as:

- workflow reference
- patch source
- customization logic reference

And treat `rustdesk` as:

- the actual build workspace

## Suggested Local Build Bootstrap

### Clone upstream RustDesk

```bash
cd ~/Github
git clone --recursive https://github.com/rustdesk/rustdesk.git
cd rustdesk
git checkout 1.4.6
git submodule update --init --recursive
```

### macOS prerequisites on your Mac

```bash
brew install imagemagick potrace nasm cmake gcc wget ninja llvm create-dmg pkg-config
rustup toolchain install 1.81
rustup toolchain install 1.75
```

Install separately:

- Xcode
- CocoaPods
- Flutter `3.24.5`
- `vcpkg`

### Android prerequisites on your Mac

Install:

- Android Studio
- Android SDK platform tools
- Android NDK `r27c`
- Java 17
- Flutter `3.24.5`

Then:

```bash
rustup toolchain install 1.75
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android
cargo +1.75 install cargo-ndk --version 3.1.2 --locked
```

## Important Caveats

### Android workflow is CI-tested on Ubuntu, not on macOS

The Android pipeline in this repo runs on `ubuntu-24.04`, not on macOS.

Source:

- [generator-android.yml](/Users/savannachow/Github/rdgen/.github/workflows/generator-android.yml#L57)

So building Android on your Mac is feasible, but this repo does not prove that exact local macOS host path end-to-end. You will need to translate the Linux package/tool setup into the equivalent macOS Android toolchain install.

### macOS build changes upstream files aggressively

The macOS workflow relies on many `sed` edits into upstream RustDesk files. This means upgrades to a newer upstream RustDesk tag can break the customization process even if the base app still builds.

### This repo does not provide a local wrapper script

There is no checked-in script here that does:

- clone RustDesk
- apply rdgen patches
- inject config/icons
- run macOS build
- run Android build

That orchestration only exists in GitHub Actions YAML today.

## Practical Conclusion

If your question is "can this repo by itself build RustDesk macOS and Android apps locally?" the answer is:

**No, not by itself.**

If your question is "does this repo contain enough information to reconstruct a local build pipeline?" the answer is:

**Mostly yes, but only when combined with upstream `rustdesk/rustdesk`, local platform SDKs, and your signing assets.**

## Best Next Step

The right next step is to create a local helper script that:

1. clones or updates `rustdesk/rustdesk`
2. checks out `1.4.6` or `master`
3. applies the same customizations from rdgen workflows
4. runs a local macOS build
5. runs a local Android build

That would turn this from a GitHub Actions-only generator into a reproducible local build process on your machine.
