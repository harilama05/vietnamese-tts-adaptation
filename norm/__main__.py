"""CLI: python -m vietnamese_tts_normalizer --explain 'Giá 0.5kg là 50.000đ'."""

import argparse
import json
import sys
from dataclasses import asdict, fields

from . import Normalizer, NormalizerConfig, __version__


def main():
    parser = argparse.ArgumentParser(description="Vietnamese TTS text normalization")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("text", nargs="*", help="Text; read stdin when omitted")
    parser.add_argument("--locale", choices=("auto", "vi", "en"), default="auto")
    parser.add_argument("--acronyms", choices=("latin", "spell", "preserve"), default=None,
                        help="Acronyms outside the common table: latin (default, G D P), spell (0.10.0 Vietnamese letter names) or preserve")
    parser.add_argument("--abbreviations", choices=("common", "extended", "none"), default=None,
                        help="common (default), extended (0.9.x dictionary) or none")
    parser.add_argument("--ambiguous-number", choices=("infer", "vi", "en", "preserve"), default=None,
                        help="Reading of 1.234/1,234 when --locale is auto (default infer)")
    parser.add_argument("--links", choices=("preserve", "speak"), default="preserve")
    parser.add_argument("--duration-format", choices=("clock", "mm:ss", "hh:mm"), default="clock")
    parser.add_argument("--domains", help="Comma-separated domain names; empty string disables domain rules")
    parser.add_argument("--content-profile", choices=("omnivoice", "plain_text"), default="omnivoice")
    parser.add_argument("--jsonl", action="store_true", help="Stream stdin objects with text and optional id; one JSON result per line")
    parser.add_argument("--config", help="JSON file of NormalizerConfig fields and overrides")
    parser.add_argument("--explain", action="store_true", help="Emit JSON with source-span decisions")
    args = parser.parse_args()
    values = {"number_locale": args.locale, "link_mode": args.links, "duration_format": args.duration_format}
    values["content_profile"] = args.content_profile
    # Unset policy flags must not override NormalizerConfig defaults.
    for name, value in (("acronym_mode", args.acronyms), ("abbreviation_policy", args.abbreviations),
                        ("ambiguous_number", args.ambiguous_number)):
        if value is not None:
            values[name] = value
    if args.domains is not None:
        values["enabled_domains"] = [value.strip() for value in args.domains.split(",") if value.strip()]
    if args.config:
        with open(args.config, encoding="utf-8") as stream:
            values.update(json.load(stream))
    try:
        normalizer = Normalizer(NormalizerConfig(**values))
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    if args.jsonl:
        if args.text:
            parser.error("--jsonl reads stdin and cannot be combined with positional text")
        return _jsonl(normalizer, explain=args.explain)
    text = " ".join(args.text) if args.text else sys.stdin.read()
    if args.explain:
        print(json.dumps(asdict(normalizer.normalize_with_trace(text)), ensure_ascii=False, indent=2))
    else:
        print(normalizer.normalize(text))
    return 0


def _jsonl(normalizer, *, explain):
    config = {field.name: getattr(normalizer.config, field.name) for field in fields(normalizer.config)}
    for name in ("abbreviation_overrides", "unit_overrides"):
        config[name] = dict(config[name])
    failed = False
    for line_number, line in enumerate(sys.stdin, 1):
        if not line.strip():
            continue
        payload = {"line": line_number, "version": __version__}
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise ValueError("each record must be an object with a string text field")
            if set(row) - {"id", "text"}:
                raise ValueError("only id and text fields are supported; use --config for shared settings")
            if "id" in row:
                payload["id"] = row["id"]
            if explain:
                payload.update(asdict(normalizer.normalize_with_trace(row["text"])))
            else:
                payload["text"] = normalizer.normalize(row["text"])
            payload["config"] = config
        except (ValueError, TypeError) as exc:
            failed = True
            payload["error"] = str(exc)
        print(json.dumps(payload, ensure_ascii=False))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
