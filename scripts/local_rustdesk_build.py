#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PATCH_DIR = REPO_ROOT / ".github" / "patches"

DEFAULTS = {
    "version": "1.4.6",
    "platforms": ["macos"],
    "source": {
        "repo_url": "https://github.com/rustdesk/rustdesk.git",
        "cache_dir": str(REPO_ROOT / ".cache" / "rustdesk-src"),
        "workspace_root": str(REPO_ROOT / "build" / "workspaces"),
        "dist_root": str(REPO_ROOT / "dist"),
    },
    "app_name": "rustdesk",
    "filename": "rustdesk",
    "company_name": "Purslane Ltd",
    "server": "rs-ny.rustdesk.com",
    "key": "OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=",
    "api_server": "",
    "url_link": "https://rustdesk.com",
    "download_link": "https://rustdesk.com/download",
    "android_app_id": "com.carriez.flutter_hbb",
    "assets": {
        "icon_path": "",
        "logo_path": "",
        "privacy_path": "",
    },
    "features": {
        "delay_fix": True,
        "cycle_monitor": False,
        "x_offline": False,
        "hide_cm": False,
        "remove_new_version_notif": False,
        "remove_setup_server_tip": True,
    },
    "client_config": {
        "direction": "both",
        "disable_installation": False,
        "disable_settings": False,
        "permanent_password": "",
        "theme": "system",
        "theme_scope": "default",
        "deny_lan": False,
        "enable_direct_ip": False,
        "auto_close": False,
        "permissions_scope": "default",
        "permissions_type": "custom",
        "permissions": {
            "keyboard": True,
            "clipboard": True,
            "file_transfer": True,
            "audio": True,
            "tcp_tunneling": True,
            "remote_restart": True,
            "recording": True,
            "blocking_input": True,
            "remote_config_modification": False,
            "printer": True,
            "camera": True,
            "terminal": True,
        },
        "verification_method": "use-both-passwords",
        "approve_mode": "password-click",
        "remove_wallpaper": True,
        "default_settings": {},
        "override_settings": {},
    },
    "toolchain": {
        "flutter_bin": "flutter",
        "cargo_bin": "cargo",
        "rustup_bin": "rustup",
        "patch_flutter_sdk": False,
        "flutter_scheduler_workaround": False,
        "vcpkg_root": str(REPO_ROOT / ".cache" / "vcpkg"),
        "vcpkg_commit": "120deac3062162151622ca4860575a33844ba10b",
        "flutter_version": "3.24.5",
        "flutter_rust_bridge_version": "1.80.1",
        "cargo_ndk_version": "3.1.2",
        "android_ndk": os.environ.get("ANDROID_NDK_ROOT", ""),
    },
    "macos": {
        "enabled": True,
        "minimum_version": "12.3",
        "screencapturekit": True,
        "create_dmg": True,
        "codesign_identity": "",
    },
    "android": {
        "enabled": False,
        "abis": ["arm64-v8a"],
        "build_mode": "release",
        "signing": {
            "keystore_path": "",
            "store_password": "",
            "key_alias": "",
            "key_password": "",
        },
    },
}

ANDROID_TARGETS = {
    "arm64-v8a": {
        "rust_target": "aarch64-linux-android",
        "ndk_script": "ndk_arm64.sh",
        "jni_dir": "arm64-v8a",
        "flutter_target": "android-arm64",
        "output_name": "app-arm64-v8a-release.apk",
    },
    "armeabi-v7a": {
        "rust_target": "armv7-linux-androideabi",
        "ndk_script": "ndk_arm.sh",
        "jni_dir": "armeabi-v7a",
        "flutter_target": "android-arm",
        "output_name": "app-armeabi-v7a-release.apk",
    },
    "x86_64": {
        "rust_target": "x86_64-linux-android",
        "ndk_script": "ndk_x64.sh",
        "jni_dir": "x86_64",
        "flutter_target": "android-x64",
        "output_name": "app-x86_64-release.apk",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def now_slug() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def normalize_bool(value: object) -> bool:
    return bool(value)


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    joined = " ".join(cmd)
    print(f"+ {joined}")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def capture(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def ensure_command(name: str) -> None:
    if shutil.which(name):
        return
    raise SystemExit(f"Missing required command: {name}")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def strip_json_comments(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < length else ""
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            while i < length and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "/":
            i += 2
            while i < length and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < length and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def replace_text(path: Path, old: str, new: str, required: bool = True) -> None:
    content = read_text(path)
    if old not in content:
        if required:
            raise RuntimeError(f"Expected text not found in {path}: {old}")
        return
    write_text(path, content.replace(old, new))


def replace_regex(path: Path, pattern: str, repl: str, required: bool = True, flags: int = 0) -> None:
    content = read_text(path)
    updated, count = re.subn(pattern, repl, content, flags=flags)
    if count == 0 and required:
        raise RuntimeError(f"Expected regex not found in {path}: {pattern}")
    if count > 0:
        write_text(path, updated)


def insert_after(path: Path, needle: str, text_to_insert: str) -> None:
    content = read_text(path)
    if text_to_insert in content:
        return
    if needle not in content:
        raise RuntimeError(f"Expected anchor not found in {path}: {needle}")
    write_text(path, content.replace(needle, f"{needle}\n{text_to_insert}", 1))


def copy_file(src: Path, dst: Path) -> None:
    ensure_parent(dst)
    shutil.copy2(src, dst)


def sanitize_ascii_filename(value: str, fallback: str) -> str:
    if not value or not value.isascii():
        return fallback
    sanitized = re.sub(r"[^\w\s-]", "_", value).strip().replace(" ", "_")
    return sanitized or fallback


def normalize_app_name(value: str) -> str:
    if not value or not value.isascii():
        return "rustdesk"
    return value


def load_config(path: Path) -> dict:
    raw_text = path.read_text(encoding="utf-8")
    user_cfg = json.loads(strip_json_comments(raw_text))
    cfg = deep_merge(DEFAULTS, user_cfg)
    if not cfg["api_server"]:
        cfg["api_server"] = f"{cfg['server']}:21114"
    cfg["app_name"] = normalize_app_name(cfg["app_name"])
    cfg["filename"] = sanitize_ascii_filename(cfg["filename"], "rustdesk")
    requested_platforms = list(cfg.get("platforms", []))
    cfg["macos"]["enabled"] = cfg["macos"]["enabled"] and "macos" in requested_platforms
    cfg["android"]["enabled"] = cfg["android"]["enabled"] or "android" in requested_platforms
    return cfg


def clone_or_update_cache(cfg: dict) -> Path:
    cache_dir = Path(cfg["source"]["cache_dir"]).expanduser()
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    repo_url = cfg["source"]["repo_url"]
    if not cache_dir.exists():
        run(["git", "clone", "--recursive", repo_url, str(cache_dir)])
    else:
        run(["git", "fetch", "--tags", "--prune", "origin"], cwd=cache_dir)
        run(["git", "submodule", "update", "--init", "--recursive"], cwd=cache_dir)
    return cache_dir


def prepare_workspace(cfg: dict) -> tuple[Path, Path]:
    cache_dir = clone_or_update_cache(cfg)
    work_root = Path(cfg["source"]["workspace_root"]).expanduser()
    dist_root = Path(cfg["source"]["dist_root"]).expanduser()
    stamp = now_slug()
    version = cfg["version"]
    ref = "master" if version in {"master", "nightly"} else version
    workspace = work_root / f"rustdesk-{version}-{stamp}"
    dist_dir = dist_root / f"rustdesk-{version}-{stamp}"
    workspace.parent.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--recursive", "--branch", ref, str(cache_dir), str(workspace)])
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=workspace)
    return workspace, dist_dir


def ensure_vcpkg(cfg: dict) -> Path:
    vcpkg_root = Path(cfg["toolchain"]["vcpkg_root"]).expanduser()
    vcpkg_root.parent.mkdir(parents=True, exist_ok=True)
    commit = cfg["toolchain"]["vcpkg_commit"]
    if not vcpkg_root.exists():
        run(["git", "clone", "https://github.com/microsoft/vcpkg", str(vcpkg_root)])
    run(["git", "fetch", "--tags", "--prune", "origin"], cwd=vcpkg_root)
    run(["git", "checkout", commit], cwd=vcpkg_root)
    bootstrap = vcpkg_root / "bootstrap-vcpkg.sh"
    if not (vcpkg_root / "vcpkg").exists():
        run(["bash", str(bootstrap)], cwd=vcpkg_root)
    return vcpkg_root


def find_flutter_root(flutter_bin: str) -> Path:
    flutter_path = shutil.which(flutter_bin)
    if not flutter_path:
        raise SystemExit(f"Could not find flutter binary: {flutter_bin}")
    return Path(flutter_path).resolve().parent.parent


def patch_flutter_sdk_if_requested(cfg: dict) -> None:
    flutter_bin = cfg["toolchain"]["flutter_bin"]
    flutter_root = find_flutter_root(flutter_bin)
    patch_requested = cfg["toolchain"]["patch_flutter_sdk"]
    workaround_requested = cfg["toolchain"]["flutter_scheduler_workaround"]
    if patch_requested:
        patch_file = PATCH_DIR / "flutter_3.24.4_dropdown_menu_enableFilter.diff"
        try:
            run(["git", "apply", str(patch_file)], cwd=flutter_root)
        except subprocess.CalledProcessError:
            print("warning: flutter SDK patch did not apply cleanly; continuing")
    if workaround_requested:
        binding_path = flutter_root / "packages" / "flutter" / "lib" / "src" / "scheduler" / "binding.dart"
        replace_text(
            binding_path,
            "_setFramesEnabledState(false);",
            "//_setFramesEnabledState(false);",
            required=False,
        )


def generate_custom_client_payload(cfg: dict) -> str:
    ccfg = cfg["client_config"]
    features = cfg["features"]
    payload: dict[str, object] = {
        "override-settings": {},
        "default-settings": {},
        "enable-lan-discovery": "N" if normalize_bool(ccfg["deny_lan"]) else "Y",
        "allow-auto-disconnect": "Y" if normalize_bool(ccfg["auto_close"]) else "N",
    }
    direction = str(ccfg["direction"]).lower()
    if direction != "both":
        payload["conn-type"] = direction
    if normalize_bool(ccfg["disable_installation"]):
        payload["disable-installation"] = "Y"
    if normalize_bool(ccfg["disable_settings"]):
        payload["disable-settings"] = "Y"
    if cfg["app_name"].lower() != "rustdesk":
        payload["app-name"] = cfg["app_name"]
    if ccfg["permanent_password"]:
        payload["password"] = ccfg["permanent_password"]
    theme = str(ccfg["theme"])
    theme_scope = str(ccfg["theme_scope"])
    if theme != "system":
        payload[f"{theme_scope}-settings"]["theme"] = theme
    perm_scope = str(ccfg["permissions_scope"])
    settings_bucket = payload[f"{perm_scope}-settings"]
    assert isinstance(settings_bucket, dict)
    settings_bucket["access-mode"] = ccfg["permissions_type"]
    permissions = ccfg["permissions"]
    settings_bucket["enable-keyboard"] = "Y" if normalize_bool(permissions["keyboard"]) else "N"
    settings_bucket["enable-clipboard"] = "Y" if normalize_bool(permissions["clipboard"]) else "N"
    settings_bucket["enable-file-transfer"] = "Y" if normalize_bool(permissions["file_transfer"]) else "N"
    settings_bucket["enable-audio"] = "Y" if normalize_bool(permissions["audio"]) else "N"
    settings_bucket["enable-tunnel"] = "Y" if normalize_bool(permissions["tcp_tunneling"]) else "N"
    settings_bucket["enable-remote-restart"] = "Y" if normalize_bool(permissions["remote_restart"]) else "N"
    settings_bucket["enable-record-session"] = "Y" if normalize_bool(permissions["recording"]) else "N"
    settings_bucket["enable-block-input"] = "Y" if normalize_bool(permissions["blocking_input"]) else "N"
    settings_bucket["allow-remote-config-modification"] = "Y" if normalize_bool(permissions["remote_config_modification"]) else "N"
    settings_bucket["direct-server"] = "Y" if normalize_bool(ccfg["enable_direct_ip"]) else "N"
    settings_bucket["verification-method"] = ccfg["verification_method"]
    settings_bucket["approve-mode"] = ccfg["approve_mode"]
    settings_bucket["allow-hide-cm"] = "Y" if normalize_bool(features["hide_cm"]) else "N"
    settings_bucket["allow-remove-wallpaper"] = "Y" if normalize_bool(ccfg["remove_wallpaper"]) else "N"
    settings_bucket["enable-remote-printer"] = "Y" if normalize_bool(permissions["printer"]) else "N"
    settings_bucket["enable-camera"] = "Y" if normalize_bool(permissions["camera"]) else "N"
    settings_bucket["enable-terminal"] = "Y" if normalize_bool(permissions["terminal"]) else "N"

    for key, value in ccfg["default_settings"].items():
        payload["default-settings"][key] = value
    for key, value in ccfg["override_settings"].items():
        payload["override-settings"][key] = value
    raw = json.dumps(payload, separators=(",", ":"))
    return base64.b64encode(raw.encode("ascii")).decode("ascii")


def apply_allow_custom_patch(workspace: Path) -> None:
    run([sys.executable, str(PATCH_DIR / "allowCustom.py")], cwd=workspace)


def apply_repo_patch(workspace: Path, patch_name: str) -> None:
    run(["git", "apply", str(PATCH_DIR / patch_name)], cwd=workspace)


def try_apply_repo_patch(workspace: Path, patch_name: str) -> bool:
    patch_path = PATCH_DIR / patch_name
    print(f"+ git apply {patch_path}")
    result = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def apply_remove_new_version_notif_patch(workspace: Path) -> None:
    if try_apply_repo_patch(workspace, "removeNewVersionNotif.diff"):
        return
    target = workspace / "flutter" / "lib" / "desktop" / "pages" / "desktop_home_page.dart"
    replace_text(
        target,
        "if (!bind.isCustomClient() &&",
        "if (false && !bind.isCustomClient() &&",
        required=False,
    )
    replace_text(
        target,
        "if (systemError.isNotEmpty) {",
        "if (false && systemError.isNotEmpty) {",
        required=False,
    )


def patch_common_values(cfg: dict, workspace: Path) -> None:
    replace_text(workspace / "libs" / "hbb_common" / "src" / "config.rs", "rs-ny.rustdesk.com", cfg["server"])
    replace_text(workspace / "libs" / "hbb_common" / "src" / "config.rs", "OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=", cfg["key"])
    replace_text(workspace / "src" / "common.rs", "https://admin.rustdesk.com", cfg["api_server"])

    if cfg["url_link"] != "https://rustdesk.com":
        replacements = [
            (workspace / "build.py", "https://rustdesk.com", cfg["url_link"]),
            (workspace / "flutter" / "lib" / "common.dart", "launchUrl(Uri.parse('https://rustdesk.com'));", f"launchUrl(Uri.parse('{cfg['url_link']}'));"),
            (workspace / "flutter" / "lib" / "desktop" / "pages" / "desktop_setting_page.dart", "launchUrlString('https://rustdesk.com');", f"launchUrlString('{cfg['url_link']}');"),
            (workspace / "flutter" / "lib" / "desktop" / "pages" / "desktop_setting_page.dart", "launchUrlString('https://rustdesk.com/privacy.html')", f"launchUrlString('{cfg['url_link']}/privacy.html')"),
            (workspace / "flutter" / "lib" / "mobile" / "pages" / "settings_page.dart", "const url = 'https://rustdesk.com/';", f"const url = '{cfg['url_link']}';"),
            (workspace / "flutter" / "lib" / "mobile" / "pages" / "settings_page.dart", "launchUrlString('https://rustdesk.com/privacy.html')", f"launchUrlString('{cfg['url_link']}/privacy.html')"),
            (workspace / "flutter" / "lib" / "desktop" / "pages" / "install_page.dart", "https://rustdesk.com/privacy.html", f"{cfg['url_link']}/privacy.html"),
        ]
        for path, old, new in replacements:
            replace_text(path, old, new, required=False)

    if cfg["download_link"] != "https://rustdesk.com/download":
        for path in [
            workspace / "flutter" / "lib" / "desktop" / "pages" / "desktop_home_page.dart",
            workspace / "flutter" / "lib" / "mobile" / "pages" / "connection_page.dart",
            workspace / "src" / "ui" / "index.tis",
        ]:
            replace_text(path, "https://rustdesk.com/download", cfg["download_link"], required=False)


def patch_branding(cfg: dict, workspace: Path) -> None:
    app_name = cfg["app_name"]
    company_name = cfg["company_name"]
    replace_text(workspace / "Cargo.toml", 'description = "RustDesk Remote Desktop"', f'description = "{app_name}"', required=False)
    replace_text(workspace / "Cargo.toml", 'ProductName = "RustDesk"', f'ProductName = "{app_name}"', required=False)
    replace_text(workspace / "Cargo.toml", 'FileDescription = "RustDesk Remote Desktop"', f'FileDescription = "{app_name}"', required=False)
    replace_text(workspace / "libs" / "portable" / "Cargo.toml", 'description = "RustDesk Remote Desktop"', f'description = "{app_name}"', required=False)
    replace_text(workspace / "libs" / "portable" / "Cargo.toml", 'ProductName = "RustDesk"', f'ProductName = "{app_name}"', required=False)
    replace_text(workspace / "libs" / "portable" / "Cargo.toml", 'FileDescription = "RustDesk Remote Desktop"', f'FileDescription = "{app_name}"', required=False)
    replace_text(workspace / "libs" / "portable" / "src" / "main.rs", 'const APP_PREFIX: &str = "rustdesk";', f'const APP_PREFIX: &str = "{app_name}";', required=False)
    replace_text(workspace / "flutter" / "lib" / "main.dart", "title: 'RustDesk'", f"title: '{app_name}'", required=False)
    replace_text(workspace / "flutter" / "lib" / "web" / "bridge.dart", "return 'RustDesk';", f"return '{app_name}';", required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "res" / "values" / "strings.xml", "RustDesk", app_name, required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "AndroidManifest.xml", 'android:label="RustDesk"', f'android:label="{app_name}"', required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "AndroidManifest.xml", 'android:label="RustDesk Input"', f'android:label="{app_name} Input"', required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "BootReceiver.kt", "RustDesk is Open", f"{app_name} is Open", required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "FloatingWindowService.kt", "Show Rustdesk", f"Show {app_name}", required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "MainService.kt", '"RustDesk"', f'"{app_name}"', required=False)
    replace_text(workspace / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "MainService.kt", '"RustDesk Service"', f'"{app_name} Service"', required=False)
    replace_text(workspace / "flutter" / "lib" / "desktop" / "widgets" / "tabbar_widget.dart", '"RustDesk"', f'"{app_name}"', required=False)

    for lang_file in (workspace / "src" / "lang").glob("*.rs"):
        replace_text(lang_file, "RustDesk", app_name, required=False)

    replace_text(workspace / "flutter" / "macos" / "Runner" / "Info.plist", "<string>RustDesk</string>", f"<string>{app_name}</string>", required=False)
    replace_text(workspace / "flutter" / "macos" / "Runner" / "Configs" / "AppInfo.xcconfig", "PRODUCT_NAME = RustDesk", f"PRODUCT_NAME = {app_name}", required=False)
    replace_text(workspace / "flutter" / "macos" / "Runner" / "Configs" / "AppInfo.xcconfig", "PRODUCT_BUNDLE_IDENTIFIER = com.carriez.rustdesk", f"PRODUCT_BUNDLE_IDENTIFIER = com.{app_name}.app", required=False)
    replace_text(workspace / "flutter" / "macos" / "Runner" / "Configs" / "AppInfo.xcconfig", "Purslane Ltd.", company_name, required=False)
    replace_text(workspace / "Cargo.toml", "Purslane Ltd.", company_name, required=False)
    replace_text(workspace / "libs" / "portable" / "Cargo.toml", "Purslane Ltd", company_name, required=False)
    replace_text(workspace / "flutter" / "macos" / "Runner.xcodeproj" / "project.pbxproj", 'PRODUCT_NAME = "RustDesk"', f'PRODUCT_NAME = "{app_name}"', required=False)
    replace_regex(
        workspace / "flutter" / "macos" / "Runner.xcodeproj" / "project.pbxproj",
        r'PRODUCT_BUNDLE_IDENTIFIER = ".*"',
        f'PRODUCT_BUNDLE_IDENTIFIER = "com.{app_name}.app"',
        required=False,
    )
    if (workspace / "flutter" / "macos" / "CMakeLists.txt").exists():
        replace_regex(
            workspace / "flutter" / "macos" / "CMakeLists.txt",
            r'set\(BINARY_NAME ".*"\)',
            f'set(BINARY_NAME "{app_name}")',
            required=False,
        )


def patch_android_values(cfg: dict, workspace: Path) -> None:
    if cfg["android_app_id"] != "com.carriez.flutter_hbb":
        replace_text(
            workspace / "flutter" / "android" / "app" / "build.gradle",
            'applicationId "com.carriez.flutter_hbb"',
            f'applicationId "{cfg["android_app_id"]}"',
            required=False,
        )
    gradle_properties = workspace / "flutter" / "android" / "gradle.properties"
    replace_text(gradle_properties, "org.gradle.jvmargs=-Xmx1024M", "org.gradle.jvmargs=-Xmx2g", required=False)


def patch_macos_values(cfg: dict, workspace: Path) -> None:
    minimum_version = cfg["macos"]["minimum_version"]
    replace_regex(workspace / "build.py", r"MACOSX_DEPLOYMENT_TARGET\=[0-9]*\.[0-9]*", f"MACOSX_DEPLOYMENT_TARGET={minimum_version}", required=False)
    replace_regex(workspace / "flutter" / "macos" / "Podfile", r"platform :osx, '.*'", f"platform :osx, '{minimum_version}'", required=False)
    replace_regex(workspace / "Cargo.toml", r'osx_minimum_system_version = "[0-9]*\.[0-9]*"', f'osx_minimum_system_version = "{minimum_version}"', required=False)
    replace_regex(
        workspace / "flutter" / "macos" / "Runner.xcodeproj" / "project.pbxproj",
        r"MACOSX_DEPLOYMENT_TARGET = [0-9]*\.[0-9]*;",
        f"MACOSX_DEPLOYMENT_TARGET = {minimum_version};",
        required=False,
    )
    replace_text(workspace / "build.py", "RustDesk.app", f'"{cfg["app_name"]}.app"', required=False)


def copy_logo_if_needed(cfg: dict, workspace: Path) -> None:
    logo_path = Path(cfg["assets"]["logo_path"]).expanduser()
    if not str(logo_path):
        return
    if not logo_path.exists():
        raise SystemExit(f"Logo not found: {logo_path}")
    copy_file(logo_path, workspace / "flutter" / "assets" / "logo.png")


def prepare_icon_assets(cfg: dict, workspace: Path) -> None:
    icon_cfg = cfg["assets"]["icon_path"]
    if not icon_cfg:
        return
    icon_path = Path(icon_cfg).expanduser()
    if not icon_path.exists():
        raise SystemExit(f"Icon not found: {icon_path}")
    for cmd_name in ["magick", "potrace", "iconutil"]:
        ensure_command(cmd_name)

    res_dir = workspace / "res"
    flutter_assets = workspace / "flutter" / "assets"
    appicon_dir = workspace / "flutter" / "macos" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"
    res_dir.mkdir(parents=True, exist_ok=True)
    flutter_assets.mkdir(parents=True, exist_ok=True)
    appicon_dir.mkdir(parents=True, exist_ok=True)

    copy_file(icon_path, res_dir / "icon.png")
    run(["magick", str(res_dir / "icon.png"), "-resize", "32x32", str(res_dir / "32x32.png")])
    run(["magick", str(res_dir / "icon.png"), "-resize", "64x64", str(res_dir / "64x64.png")])
    run(["magick", str(res_dir / "icon.png"), "-resize", "128x128", str(res_dir / "128x128.png")])
    run(["magick", str(res_dir / "128x128.png"), "-resize", "200%", str(res_dir / "128x128@2x.png")])
    run(["magick", str(res_dir / "icon.png"), "-resize", "128x128", str(res_dir / "mac-icon.png")])
    run(["magick", str(res_dir / "icon.png"), "-resize", "22x22", "-colorspace", "gray", "-alpha", "set", "-background", "none", "-channel", "A", "-evaluate", "set", "100%", str(res_dir / "mac-tray-dark-x2.png")])
    run(["magick", str(res_dir / "icon.png"), "-resize", "22x22", "-negate", "-colorspace", "gray", "-alpha", "set", "-background", "none", "-channel", "A", "-evaluate", "set", "100%", str(res_dir / "mac-tray-light-x2.png")])
    run(["magick", str(res_dir / "icon.png"), "-flatten", str(workspace / "temp_icon.pbm")])
    run(["potrace", "--svg", "-o", str(flutter_assets / "icon.svg"), str(workspace / "temp_icon.pbm")])
    copy_file(res_dir / "icon.png", flutter_assets / "icon.png")
    if (workspace / "temp_icon.pbm").exists():
        (workspace / "temp_icon.pbm").unlink()

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        run(["magick", str(res_dir / "icon.png"), "-resize", f"{size}x{size}", str(appicon_dir / f"app_icon_{size}.png")])

    contents_json = {
        "images": [
            {"size": "16x16", "idiom": "mac", "filename": "app_icon_16.png", "scale": "1x"},
            {"size": "16x16", "idiom": "mac", "filename": "app_icon_32.png", "scale": "2x"},
            {"size": "32x32", "idiom": "mac", "filename": "app_icon_32.png", "scale": "1x"},
            {"size": "32x32", "idiom": "mac", "filename": "app_icon_64.png", "scale": "2x"},
            {"size": "128x128", "idiom": "mac", "filename": "app_icon_128.png", "scale": "1x"},
            {"size": "128x128", "idiom": "mac", "filename": "app_icon_256.png", "scale": "2x"},
            {"size": "256x256", "idiom": "mac", "filename": "app_icon_256.png", "scale": "1x"},
            {"size": "256x256", "idiom": "mac", "filename": "app_icon_512.png", "scale": "2x"},
            {"size": "512x512", "idiom": "mac", "filename": "app_icon_512.png", "scale": "1x"},
            {"size": "512x512", "idiom": "mac", "filename": "app_icon_1024.png", "scale": "2x"},
        ],
        "info": {"version": 1, "author": "xcode"},
    }
    write_text(appicon_dir / "Contents.json", json.dumps(contents_json, indent=2))

    iconset_dir = workspace / "iconset.iconset"
    iconset_dir.mkdir(exist_ok=True)
    for src, dst in [
        ("app_icon_16.png", "icon_16x16.png"),
        ("app_icon_32.png", "icon_16x16@2x.png"),
        ("app_icon_32.png", "icon_32x32.png"),
        ("app_icon_64.png", "icon_32x32@2x.png"),
        ("app_icon_128.png", "icon_128x128.png"),
        ("app_icon_256.png", "icon_128x128@2x.png"),
        ("app_icon_256.png", "icon_256x256.png"),
        ("app_icon_512.png", "icon_256x256@2x.png"),
        ("app_icon_512.png", "icon_512x512.png"),
        ("app_icon_1024.png", "icon_512x512@2x.png"),
    ]:
        copy_file(appicon_dir / src, iconset_dir / dst)
    run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(workspace / "flutter" / "macos" / "Runner" / "AppIcon.icns")])
    shutil.rmtree(iconset_dir, ignore_errors=True)

    insert_after(workspace / "flutter" / "pubspec.yaml", "  image_path: \"../res/icon.png\"", "  adaptive_icon_background: \"#ffffff\"\n  adaptive_icon_foreground: \"../res/icon.png\"\n  adaptive_icon_foreground_inset: 32")
    run([cfg["toolchain"]["flutter_bin"], "pub", "get"], cwd=workspace / "flutter")
    run([cfg["toolchain"]["flutter_bin"], "pub", "run", "flutter_launcher_icons"], cwd=workspace / "flutter")
    replace_regex(workspace / "src" / "ui.rs", r'iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHL.*?"', f'{base64.b64encode((res_dir / "icon.png").read_bytes()).decode("ascii")}"', required=False)
    replace_regex(workspace / "flutter" / "android" / "app" / "src" / "main" / "res" / "values" / "colors.xml", r".*ic_launcher_background.*\n?", "", required=False)


def ensure_archive_override(workspace: Path) -> None:
    insert_after(workspace / "flutter" / "pubspec.yaml", "  intl: ^0.19.0", "  archive: ^3.6.1")


def prepare_custom_asset(cfg: dict, workspace: Path) -> None:
    custom_payload = generate_custom_client_payload(cfg)
    assets_dir = workspace / "flutter" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    write_text(assets_dir / "custom_.txt", custom_payload)


def generate_bridge(cfg: dict, workspace: Path) -> None:
    cargo_bin = cfg["toolchain"]["cargo_bin"]
    flutter_bin = cfg["toolchain"]["flutter_bin"]
    frb_version = cfg["toolchain"]["flutter_rust_bridge_version"]
    replace_text(workspace / "flutter" / "pubspec.yaml", "extended_text: 14.0.0", "extended_text: 13.0.0", required=False)
    run([cargo_bin, "install", "cargo-expand", "--version", "1.0.95", "--locked"])
    run([cargo_bin, "install", "flutter_rust_bridge_codegen", "--version", frb_version, "--features", "uuid", "--locked"])
    run([flutter_bin, "pub", "get"], cwd=workspace / "flutter")
    codegen_bin = Path.home() / ".cargo" / "bin" / "flutter_rust_bridge_codegen"
    if not codegen_bin.exists():
        codegen_bin = Path(shutil.which("flutter_rust_bridge_codegen") or "")
    if not codegen_bin.exists():
        raise SystemExit("flutter_rust_bridge_codegen was not installed successfully")
    run(
        [
            str(codegen_bin),
            "--rust-input",
            "./src/flutter_ffi.rs",
            "--dart-output",
            "./flutter/lib/generated_bridge.dart",
            "--c-output",
            "./flutter/macos/Runner/bridge_generated.h",
        ],
        cwd=workspace,
    )
    copy_file(workspace / "flutter" / "macos" / "Runner" / "bridge_generated.h", workspace / "flutter" / "ios" / "Runner" / "bridge_generated.h")


def prepare_workspace_customizations(cfg: dict, workspace: Path) -> None:
    patch_flutter_sdk_if_requested(cfg)
    ensure_archive_override(workspace)
    apply_allow_custom_patch(workspace)
    if normalize_bool(cfg["features"]["remove_setup_server_tip"]):
        apply_repo_patch(workspace, "removeSetupServerTip.diff")
    if normalize_bool(cfg["features"]["cycle_monitor"]):
        apply_repo_patch(workspace, "cycle_monitor.diff")
    if normalize_bool(cfg["features"]["x_offline"]):
        apply_repo_patch(workspace, "xoffline.diff")
    if normalize_bool(cfg["features"]["hide_cm"]):
        apply_repo_patch(workspace, "hidecm.diff")
    if normalize_bool(cfg["features"]["remove_new_version_notif"]):
        apply_remove_new_version_notif_patch(workspace)
    patch_common_values(cfg, workspace)
    patch_branding(cfg, workspace)
    patch_android_values(cfg, workspace)
    patch_macos_values(cfg, workspace)
    if normalize_bool(cfg["features"]["delay_fix"]):
        replace_text(workspace / "src" / "client.rs", "!key.is_empty()", "false", required=False)
    copy_logo_if_needed(cfg, workspace)
    prepare_custom_asset(cfg, workspace)
    prepare_icon_assets(cfg, workspace)
    if cfg["assets"]["privacy_path"]:
        print("warning: privacy_path is currently not wired into macOS/Android local builds")
    generate_bridge(cfg, workspace)


def build_macos(cfg: dict, workspace: Path, dist_dir: Path, env: dict[str, str]) -> None:
    flutter_bin = cfg["toolchain"]["flutter_bin"]
    run([flutter_bin, "pub", "get"], cwd=workspace / "flutter", env=env)
    install_root = Path(env["VCPKG_ROOT"]) / "installed"
    run([str(Path(env["VCPKG_ROOT"]) / "vcpkg"), "install", f"--x-install-root={install_root}"], cwd=workspace, env=env)
    cmd = [sys.executable, "build.py", "--flutter", "--hwcodec", "--unix-file-copy-paste"]
    if normalize_bool(cfg["macos"]["screencapturekit"]):
        cmd.append("--screencapturekit")
    run(cmd, cwd=workspace, env=env)

    app_name = cfg["app_name"]
    built_app = workspace / "flutter" / "build" / "macos" / "Build" / "Products" / "Release" / f"{app_name}.app"
    if not built_app.exists():
        fallback = workspace / "flutter" / "build" / "macos" / "Build" / "Products" / "Release" / "RustDesk.app"
        built_app = fallback
    if not built_app.exists():
        raise SystemExit("macOS build finished but no .app bundle was found")

    if cfg["assets"]["logo_path"]:
        logo_dst = built_app / "Contents" / "Frameworks" / "App.framework" / "Versions" / "Current" / "Resources" / "flutter_assets" / "assets" / "logo.png"
        copy_file(Path(cfg["assets"]["logo_path"]).expanduser(), logo_dst)

    if cfg["macos"]["codesign_identity"]:
        run(["codesign", "-s", cfg["macos"]["codesign_identity"], "--force", "--options", "runtime", str(built_app)], cwd=workspace)

    output_app = dist_dir / f"{cfg['filename']}.app"
    if output_app.exists():
        shutil.rmtree(output_app)
    shutil.copytree(built_app, output_app)
    print(f"macOS app: {output_app}")

    if normalize_bool(cfg["macos"]["create_dmg"]):
        dmg_path = dist_dir / f"{cfg['filename']}.dmg"
        run(
            [
                "hdiutil",
                "create",
                "-volname",
                cfg["app_name"],
                "-srcfolder",
                str(output_app),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_path),
            ],
            cwd=dist_dir,
        )
        print(f"macOS dmg: {dmg_path}")


def find_ndk_libcpp(ndk_root: Path, rust_target: str) -> Path:
    prebuilt_dir = ndk_root / "toolchains" / "llvm" / "prebuilt"
    if not prebuilt_dir.exists():
        raise SystemExit(f"Invalid Android NDK path: {ndk_root}")
    candidates = [p for p in prebuilt_dir.iterdir() if p.is_dir()]
    if not candidates:
        raise SystemExit(f"No NDK prebuilt toolchain found under: {prebuilt_dir}")
    libcxx = candidates[0] / "sysroot" / "usr" / "lib" / rust_target / "libc++_shared.so"
    if not libcxx.exists():
        raise SystemExit(f"Missing libc++_shared.so for {rust_target}: {libcxx}")
    return libcxx


def write_android_signing(cfg: dict, workspace: Path) -> bool:
    signing = cfg["android"]["signing"]
    key_path = signing["keystore_path"]
    build_gradle = workspace / "flutter" / "android" / "app" / "build.gradle"
    if key_path:
        key_properties = "\n".join(
            [
                f"storePassword={signing['store_password']}",
                f"keyPassword={signing['key_password']}",
                f"keyAlias={signing['key_alias']}",
                f"storeFile={Path(key_path).expanduser()}",
            ]
        )
        write_text(workspace / "flutter" / "android" / "key.properties", key_properties + "\n")
        return True
    replace_text(build_gradle, "signingConfig signingConfigs.release", "signingConfig signingConfigs.debug", required=False)
    return False


def build_android(cfg: dict, workspace: Path, dist_dir: Path, env: dict[str, str]) -> None:
    flutter_bin = cfg["toolchain"]["flutter_bin"]
    cargo_bin = cfg["toolchain"]["cargo_bin"]
    rustup_bin = cfg["toolchain"]["rustup_bin"]
    ndk_root = Path(cfg["toolchain"]["android_ndk"]).expanduser()
    if not str(ndk_root):
        raise SystemExit("toolchain.android_ndk is required for Android builds")
    if not ndk_root.exists():
        raise SystemExit(f"Android NDK not found: {ndk_root}")

    write_android_signing(cfg, workspace)
    run([flutter_bin, "pub", "get"], cwd=workspace / "flutter", env=env)
    run([cargo_bin, "install", "cargo-ndk", "--version", cfg["toolchain"]["cargo_ndk_version"], "--locked"], cwd=workspace, env=env)

    install_root = Path(env["VCPKG_ROOT"]) / "installed"
    for abi in cfg["android"]["abis"]:
        if abi not in ANDROID_TARGETS:
            raise SystemExit(f"Unsupported Android ABI: {abi}")
        target_meta = ANDROID_TARGETS[abi]
        rust_target = target_meta["rust_target"]
        run([rustup_bin, "target", "add", rust_target], cwd=workspace, env=env)
        run(["bash", str(workspace / "flutter" / "build_android_deps.sh"), abi], cwd=workspace, env=env)
        run([str(Path(env["VCPKG_ROOT"]) / "vcpkg"), "install", f"--x-install-root={install_root}"], cwd=workspace, env=env)
        run(["bash", str(workspace / "flutter" / target_meta["ndk_script"])], cwd=workspace, env=env)

        jni_dir = workspace / "flutter" / "android" / "app" / "src" / "main" / "jniLibs" / target_meta["jni_dir"]
        jni_dir.mkdir(parents=True, exist_ok=True)
        copy_file(workspace / "target" / rust_target / "release" / "liblibrustdesk.so", jni_dir / "librustdesk.so")
        copy_file(find_ndk_libcpp(ndk_root, rust_target), jni_dir / "libc++_shared.so")

        run(
            [
                flutter_bin,
                "build",
                "apk",
                f"--{cfg['android']['build_mode']}",
                "--target-platform",
                target_meta["flutter_target"],
                "--split-per-abi",
            ],
            cwd=workspace / "flutter",
            env=env,
        )
        apk_name = target_meta["output_name"].replace("-release.apk", f"-{cfg['android']['build_mode']}.apk")
        built_apk = workspace / "flutter" / "build" / "app" / "outputs" / "flutter-apk" / apk_name
        if not built_apk.exists():
            raise SystemExit(f"Expected Android APK not found: {built_apk}")
        output_apk = dist_dir / f"{cfg['filename']}-{abi}.apk"
        copy_file(built_apk, output_apk)
        print(f"Android APK ({abi}): {output_apk}")


def build_environment(cfg: dict) -> dict[str, str]:
    env = os.environ.copy()
    vcpkg_root = ensure_vcpkg(cfg)
    env["VCPKG_ROOT"] = str(vcpkg_root)
    if cfg["toolchain"]["android_ndk"]:
        env["ANDROID_NDK_ROOT"] = str(Path(cfg["toolchain"]["android_ndk"]).expanduser())
        env["ANDROID_NDK_HOME"] = env["ANDROID_NDK_ROOT"]
    return env


def validate_host(cfg: dict) -> None:
    if platform.system() != "Darwin":
        raise SystemExit("This local build helper currently targets macOS hosts only")
    for cmd_name in ["git", "python3", cfg["toolchain"]["flutter_bin"], cfg["toolchain"]["cargo_bin"], cfg["toolchain"]["rustup_bin"]]:
        ensure_command(cmd_name)
    if cfg["macos"]["enabled"]:
        for cmd_name in ["xcodebuild", "pkg-config", "cmake", "ninja", "clang", "hdiutil"]:
            ensure_command(cmd_name)
    if cfg["android"]["enabled"]:
        for cmd_name in ["java"]:
            ensure_command(cmd_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local macOS/Android RustDesk builder with rdgen-style customization")
    parser.add_argument("--config", required=True, help="Path to local build config JSON")
    args = parser.parse_args()

    cfg = load_config(Path(args.config).expanduser())
    validate_host(cfg)
    workspace, dist_dir = prepare_workspace(cfg)
    env = build_environment(cfg)
    prepare_workspace_customizations(cfg, workspace)

    if cfg["macos"]["enabled"]:
        build_macos(cfg, workspace, dist_dir, env)
    if cfg["android"]["enabled"]:
        build_android(cfg, workspace, dist_dir, env)

    summary = {
        "workspace": str(workspace),
        "dist_dir": str(dist_dir),
        "version": cfg["version"],
        "platforms": cfg["platforms"],
    }
    write_text(dist_dir / "build-summary.json", json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
