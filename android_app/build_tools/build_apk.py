#!/usr/bin/env python3
"""Compila a app Android num APK assinado, sem precisar do Android SDK.

Precisa apenas de JDK (javac/java/keytool) e Python 3. As ferramentas Android
(dx, apksig e a API android.jar) são descarregadas do Maven Central.
O AndroidManifest.xml e o resources.arsc são escritos diretamente no formato
binário do Android por este script.

Uso:  python3 build_tools/build_apk.py        (a partir da pasta android_app)
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "build_tools"
CACHE = ROOT / ".cache"
OUT = ROOT / "build"
DIST = ROOT / "dist"

PACKAGE = "com.horrorbot.reddit"
APP_LABEL = "Histórias de Horror"
VERSION_CODE = 1
VERSION_NAME = "1.0"
MIN_SDK = 24  # Android 7.0+ (assinatura v2)
TARGET_SDK = 34
APK_NAME = f"historias-de-horror-{VERSION_NAME}.apk"

MAVEN = "https://repo.maven.apache.org/maven2"
DEPS = {
    "android.jar": "com/google/android/android/4.1.1.4/android-4.1.1.4.jar",
    "dx.jar": "com/jakewharton/android/repackaged/dalvik-dx/16.0.1/dalvik-dx-16.0.1.jar",
    "apksig.jar": "com/android/tools/build/apksig/2.3.0/apksig-2.3.0.jar",
    # só para compilar: o Android já inclui org.json
    "json.jar": "org/json/json/20080701/json-20080701.jar",
}

KEYSTORE = ROOT / "release.p12"
KEY_ALIAS = "horror"
KEY_PASS = os.environ.get("HORROR_KEY_PASS", "horrorstories")

# IDs dos atributos/estilos do framework (android.R.attr / android.R.style)
ATTR = {
    "theme": 0x01010000, "label": 0x01010001, "icon": 0x01010002, "name": 0x01010003,
    "exported": 0x01010010, "configChanges": 0x0101001F, "minSdkVersion": 0x0101020C,
    "versionCode": 0x0101021B, "versionName": 0x0101021C, "targetSdkVersion": 0x01010270,
    "allowBackup": 0x01010280,
}
THEME_DEVICE_DEFAULT = 0x01030128
ICON_RES_ID = 0x7F010000  # drawable/icon no nosso resources.arsc
ANDROID_NS = "http://schemas.android.com/apk/res/android"

# Tipos de Res_value
T_REF, T_STRING, T_INT_DEC, T_INT_HEX, T_BOOL = 0x01, 0x03, 0x10, 0x11, 0x12


def run(cmd: list[str], **kw) -> None:
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def fetch_deps() -> dict[str, Path]:
    CACHE.mkdir(exist_ok=True)
    paths = {}
    for name, rel in DEPS.items():
        p = CACHE / name
        if not p.exists():
            print(f"A descarregar {rel} ...")
            req = urllib.request.Request(f"{MAVEN}/{rel}", headers={"User-Agent": "horror-apk-build/1.0"})
            with urllib.request.urlopen(req) as r, open(p, "wb") as f:
                shutil.copyfileobj(r, f)
        paths[name] = p
    return paths


# ---------------------------------------------------------------- binário Android
def string_pool(strings: list[str]) -> bytes:
    """ResStringPool em UTF-16."""
    offsets, data = [], b""
    for s in strings:
        offsets.append(len(data))
        enc = s.encode("utf-16-le")
        n = len(enc) // 2
        if n > 0x7FFF:
            raise ValueError("string demasiado longa")
        data += struct.pack("<H", n) + enc + b"\x00\x00"
    data += b"\x00" * (-len(data) % 4)
    header_size = 28
    strings_start = header_size + 4 * len(strings)
    size = strings_start + len(data)
    return (struct.pack("<HHIIIIII", 0x0001, header_size, size, len(strings), 0, 0, strings_start, 0)
            + b"".join(struct.pack("<I", o) for o in offsets) + data)


class Elem:
    def __init__(self, tag: str, attrs: list[tuple] | None = None, children: list["Elem"] | None = None):
        # attrs: (ns_android: bool, name, type, value)
        self.tag, self.attrs, self.children = tag, attrs or [], children or []


def encode_axml(root: Elem) -> bytes:
    # 1) recolher strings: primeiro os nomes de atributos com ID (mapa de recursos)
    attr_names: list[str] = []
    others: list[str] = []

    def walk(e: Elem):
        for ns, name, typ, val in e.attrs:
            if ns:
                if name not in attr_names:
                    attr_names.append(name)
            elif name not in others:
                others.append(name)
            if typ == T_STRING and val not in others:
                others.append(val)
        if e.tag not in others:
            others.append(e.tag)
        for c in e.children:
            walk(c)

    walk(root)
    attr_names.sort(key=lambda n: ATTR[n])
    for extra in ("android", ANDROID_NS):
        if extra not in others:
            others.append(extra)
    strings = attr_names + [s for s in others if s not in attr_names]
    idx = {s: i for i, s in enumerate(strings)}

    chunks = [string_pool(strings)]
    resmap = b"".join(struct.pack("<I", ATTR[n]) for n in attr_names)
    chunks.append(struct.pack("<HHI", 0x0180, 8, 8 + len(resmap)) + resmap)

    NONE = 0xFFFFFFFF
    ns_body = struct.pack("<II", idx["android"], idx[ANDROID_NS])
    chunks.append(struct.pack("<HHIII", 0x0100, 16, 24, 1, NONE) + ns_body)

    def emit(e: Elem):
        attrs = sorted(e.attrs, key=lambda a: ATTR[a[1]] if a[0] else 0)
        body = b""
        for ns, name, typ, val in attrs:
            if typ == T_STRING:
                raw, data = idx[val], idx[val]
            elif typ == T_BOOL:
                raw, data = NONE, 0xFFFFFFFF if val else 0
            else:
                raw, data = NONE, val
            body += struct.pack("<IIIHBBI", idx[ANDROID_NS] if ns else NONE, idx[name], raw, 8, 0, typ, data)
        ext = struct.pack("<IIHHHHHH", NONE, idx[e.tag], 20, 20, len(attrs), 0, 0, 0)
        size = 16 + len(ext) + len(body)
        chunks.append(struct.pack("<HHIII", 0x0102, 16, size, 1, NONE) + ext + body)
        for c in e.children:
            emit(c)
        chunks.append(struct.pack("<HHIIIII", 0x0103, 16, 24, 1, NONE, NONE, idx[e.tag]))

    emit(root)
    chunks.append(struct.pack("<HHIII", 0x0101, 16, 24, 1, NONE) + ns_body)
    payload = b"".join(chunks)
    return struct.pack("<HHI", 0x0003, 8, 8 + len(payload)) + payload


def manifest() -> bytes:
    A = True
    launcher = Elem("intent-filter", [], [
        Elem("action", [(A, "name", T_STRING, "android.intent.action.MAIN")]),
        Elem("category", [(A, "name", T_STRING, "android.intent.category.LAUNCHER")]),
    ])
    config_changes = 0x0080 | 0x0020 | 0x0400 | 0x0800  # orientation|keyboardHidden|screenSize|smallestScreenSize
    root = Elem("manifest", [
        (False, "package", T_STRING, PACKAGE),
        (A, "versionCode", T_INT_DEC, VERSION_CODE),
        (A, "versionName", T_STRING, VERSION_NAME),
    ], [
        Elem("uses-sdk", [(A, "minSdkVersion", T_INT_DEC, MIN_SDK), (A, "targetSdkVersion", T_INT_DEC, TARGET_SDK)]),
        Elem("uses-permission", [(A, "name", T_STRING, "android.permission.INTERNET")]),
        Elem("application", [
            (A, "label", T_STRING, APP_LABEL),
            (A, "icon", T_REF, ICON_RES_ID),
            (A, "theme", T_REF, THEME_DEVICE_DEFAULT),
            (A, "allowBackup", T_BOOL, True),
        ], [
            Elem("activity", [
                (A, "name", T_STRING, PACKAGE + ".MainActivity"),
                (A, "exported", T_BOOL, True),
                (A, "configChanges", T_INT_HEX, config_changes),
            ], [launcher]),
            Elem("activity", [
                (A, "name", T_STRING, PACKAGE + ".StoryActivity"),
                (A, "exported", T_BOOL, False),
                (A, "configChanges", T_INT_HEX, config_changes),
            ]),
        ]),
    ])
    return encode_axml(root)


ICON_PATH = "res/drawable-xxxhdpi-v4/icon.png"


def resources_arsc() -> bytes:
    """Tabela de recursos com um único recurso: drawable/icon (0x7f010000)."""
    global_pool = string_pool([ICON_PATH])
    type_pool = string_pool(["drawable"])
    key_pool = string_pool(["icon"])

    type_spec = struct.pack("<HHIBBHI", 0x0202, 16, 16 + 4, 1, 0, 0, 1) + struct.pack("<I", 0)

    config = bytearray(64)
    struct.pack_into("<I", config, 0, 64)
    struct.pack_into("<H", config, 14, 640)   # density = xxxhdpi
    struct.pack_into("<H", config, 24, 4)     # sdkVersion = 4 (qualificador -v4)
    entry = struct.pack("<HHI", 8, 0, 0) + struct.pack("<HBBI", 8, 0, T_STRING, 0)
    header_size = 20 + len(config)
    entries_start = header_size + 4
    type_chunk = (struct.pack("<HHIBBHII", 0x0201, header_size, entries_start + len(entry), 1, 0, 0, 1, entries_start)
                  + bytes(config) + struct.pack("<I", 0) + entry)

    name = PACKAGE.encode("utf-16-le").ljust(256, b"\x00")
    pkg_header = 288
    type_strings_off = pkg_header
    key_strings_off = type_strings_off + len(type_pool)
    body = type_pool + key_pool + type_spec + type_chunk
    pkg = struct.pack("<HHII", 0x0200, pkg_header, pkg_header + len(body), 0x7F) + name + struct.pack(
        "<IIIII", type_strings_off, 1, key_strings_off, 1, 0) + body
    assert len(pkg) - len(body) == pkg_header
    payload = global_pool + pkg
    return struct.pack("<HHII", 0x0002, 12, 12 + len(payload), 1) + payload


# ---------------------------------------------------------------- ícone
def icon_png(size: int = 192) -> bytes:
    """Fantasma branco sobre fundo vermelho-escuro, desenhado em código."""
    ss = 3  # supersampling para anti-aliasing

    def color(x: float, y: float):
        cx, cy = x - 0.5, y - 0.5
        r = math.hypot(cx, cy)
        if r > 0.5:
            return None
        t = r / 0.5
        bg = (int(120 * (1 - t) + 25 * t), int(10 * (1 - t) + 4 * t), int(12 * (1 - t) + 6 * t))
        # fantasma: cabeça semicírculo + corpo + base ondulada
        gx, gy = (x - 0.5) / 0.26, (y - 0.42) / 0.26
        inside = False
        if gy <= 0 and gx * gx + gy * gy <= 1:
            inside = True
        elif 0 < gy and abs(gx) <= 1:
            wave = 1.05 + 0.13 * math.cos((gx + 1) * math.pi * 2.5)
            inside = gy <= wave
        if inside:
            # olhos e boca
            for ex in (-0.38, 0.38):
                if ((gx - ex) / 0.17) ** 2 + ((gy + 0.05) / 0.25) ** 2 <= 1:
                    return (15, 15, 15)
            if (gx / 0.16) ** 2 + ((gy - 0.42) / 0.2) ** 2 <= 1:
                return (15, 15, 15)
            return (238, 238, 238)
        return bg

    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    c = color((px + (sx + 0.5) / ss) / size, (py + (sy + 0.5) / ss) / size)
                    if c:
                        acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]; acc[3] += 255
            n = ss * ss
            a = acc[3] // n
            if a:
                cov = acc[3] / 255
                row += bytes([int(acc[0] / cov), int(acc[1] / cov), int(acc[2] / cov), a])
            else:
                row += b"\x00\x00\x00\x00"
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")


# ---------------------------------------------------------------- zip alinhado
def write_apk(path: Path, entries: list[tuple[str, bytes, bool]]) -> None:
    """Escreve o zip; entradas não comprimidas ficam alinhadas a 4 bytes (exigido p/ resources.arsc)."""
    with open(path, "wb") as raw, zipfile.ZipFile(raw, "w") as z:
        for name, data, compress in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            if compress:
                info.compress_type = zipfile.ZIP_DEFLATED
            else:
                info.compress_type = zipfile.ZIP_STORED
                base = raw.tell() + 30 + len(name.encode())
                pad = 6
                while (base + pad) % 4:
                    pad += 1
                # campo extra 0xD935 (alinhamento Android): u16 alinhamento + zeros
                info.extra = struct.pack("<HHH", 0xD935, pad - 4, 4) + b"\x00" * (pad - 6)
            z.writestr(info, data)


def check_alignment(path: Path) -> None:
    with zipfile.ZipFile(path) as z, open(path, "rb") as f:
        for info in z.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                continue
            f.seek(info.header_offset)
            hdr = f.read(30)
            n, m = struct.unpack("<HH", hdr[26:30])
            start = info.header_offset + 30 + n + m
            if start % 4:
                raise SystemExit(f"{info.filename} não está alinhado a 4 bytes ({start})")
    print("Alinhamento OK")


# ---------------------------------------------------------------- build
def main() -> int:
    deps = fetch_deps()
    if OUT.exists():
        shutil.rmtree(OUT)
    classes = OUT / "classes"
    classes.mkdir(parents=True)
    DIST.mkdir(exist_ok=True)

    sources = sorted(str(p) for p in (ROOT / "src").rglob("*.java"))
    # As classes java.* vêm da plataforma Java 8 do JDK; android.* e org.json só para compilar.
    run(["javac", "-encoding", "UTF-8", "--release", "8",
         "-cp", f"{deps['android.jar']}{os.pathsep}{deps['json.jar']}", "-d", classes, *sources])
    dex = OUT / "classes.dex"
    run(["java", "-cp", deps["dx.jar"], "com.android.dx.command.Main", "--dex",
         f"--min-sdk-version={MIN_SDK}", f"--output={dex}", classes])

    unsigned = OUT / "unsigned.apk"
    write_apk(unsigned, [
        ("AndroidManifest.xml", manifest(), True),
        ("classes.dex", dex.read_bytes(), True),
        ("resources.arsc", resources_arsc(), False),
        (ICON_PATH, icon_png(), False),
    ])

    if not KEYSTORE.exists():
        run(["keytool", "-genkeypair", "-keystore", KEYSTORE, "-storetype", "PKCS12", "-alias", KEY_ALIAS,
             "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-storepass", KEY_PASS,
             "-keypass", KEY_PASS, "-dname", "CN=Historias de Horror"])

    sign_classes = OUT / "sign"
    sign_classes.mkdir()
    run(["javac", "-cp", deps["apksig.jar"], "-d", sign_classes, TOOLS / "Sign.java"])
    final = DIST / APK_NAME
    run(["java", "--add-exports", "java.base/sun.security.x509=ALL-UNNAMED",
         "--add-exports", "java.base/sun.security.pkcs=ALL-UNNAMED",
         "--add-exports", "java.base/sun.security.util=ALL-UNNAMED", "-cp", f"{sign_classes}{os.pathsep}{deps['apksig.jar']}", "Sign",
         unsigned, final, KEYSTORE, KEY_ALIAS, KEY_PASS])
    check_alignment(final)
    print(f"\nAPK pronto: {final} ({final.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
