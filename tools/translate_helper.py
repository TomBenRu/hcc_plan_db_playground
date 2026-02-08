#!/usr/bin/env python3
"""
Qt .ts Translation Helper - Extracts unfinished translations into JSON chunks
and merges translated chunks back into .ts files.

Usage:
  python translate_helper.py extract <ts_file> [-r reference.ts] [-o output_dir] [-c chunk_size]
  python translate_helper.py merge <ts_file> <translations_dir> <output_file>

Examples:
  python translate_helper.py extract gui/translations/translations_fr.ts -r gui/translations/translations_de.ts -o fr_chunks -c 100
  python translate_helper.py merge gui/translations/translations_fr.ts fr_chunks gui/translations/translations_fr.ts
"""
import xml.etree.ElementTree as ET
import json
import os
import re
import argparse
from pathlib import Path


def extract_entries(ts_file: str, reference_ts: str | None = None,
                    output_dir: str = 'fr_chunks', chunk_size: int = 100) -> list[dict]:
    """Extract unfinished translations from a .ts file into JSON chunks.

    Each chunk contains entries with:
      - id: global index in the .ts file (for merge positioning)
      - context: the Qt context name (class/form name)
      - source_en: the English source text
      - reference_de: the German translation (if reference file provided)
    """
    tree = ET.parse(ts_file)
    root = tree.getroot()

    # Load reference translations (e.g., German) for domain context
    ref_translations: dict[tuple[str, str], str] = {}
    if reference_ts and os.path.exists(reference_ts):
        ref_tree = ET.parse(reference_ts)
        ref_root = ref_tree.getroot()
        for ctx in ref_root.findall('context'):
            ctx_name = ctx.find('name').text or ''
            for msg in ctx.findall('message'):
                src = msg.find('source')
                trans = msg.find('translation')
                src_text = src.text if src is not None and src.text else ''
                trans_text = trans.text if trans is not None and trans.text else ''
                if trans_text:
                    ref_translations[(ctx_name, src_text)] = trans_text

    entries: list[dict] = []
    global_idx = 0

    for context in root.findall('context'):
        ctx_name = context.find('name').text or ''
        for message in context.findall('message'):
            source_elem = message.find('source')
            translation_elem = message.find('translation')

            src_text = source_elem.text if source_elem is not None and source_elem.text else ''
            trans_text = translation_elem.text if translation_elem is not None and translation_elem.text else ''
            is_unfinished = (translation_elem is not None
                             and translation_elem.get('type') == 'unfinished')

            if is_unfinished and not trans_text.strip():
                entry = {
                    'id': global_idx,
                    'context': ctx_name,
                    'source_en': src_text,
                }
                ref_key = (ctx_name, src_text)
                if ref_key in ref_translations:
                    entry['reference_de'] = ref_translations[ref_key]

                entries.append(entry)
            global_idx += 1

    os.makedirs(output_dir, exist_ok=True)

    num_chunks = 0
    for i in range(0, len(entries), chunk_size):
        chunk = entries[i:i + chunk_size]
        chunk_num = i // chunk_size + 1
        filepath = os.path.join(output_dir, f'chunk_{chunk_num:03d}.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)
        num_chunks += 1

    print(f"Extracted {len(entries)} unfinished entries into {num_chunks} chunks "
          f"(chunk size: {chunk_size}) in '{output_dir}/'")
    print(f"Reference translations loaded: {len(ref_translations)}")
    return entries


def merge_translations(ts_file: str, translations_dir: str, output_file: str) -> None:
    """Merge translated JSON chunks back into the .ts file.

    Expects translated chunk files named *_translated.json with entries
    containing 'id' and 'translation_fr' fields.
    """
    # Read original file content to preserve formatting
    with open(ts_file, 'r', encoding='utf-8') as f:
        original_content = f.read()

    tree = ET.parse(ts_file)
    root = tree.getroot()

    # Load all translated chunks
    translations: dict[int, str] = {}
    for fname in sorted(os.listdir(translations_dir)):
        if fname.endswith('.json') and 'translated' in fname:
            filepath = os.path.join(translations_dir, fname)
            with open(filepath, 'r', encoding='utf-8') as f:
                chunk = json.load(f)
                for entry in chunk:
                    if 'translation_fr' in entry and entry['translation_fr']:
                        translations[entry['id']] = entry['translation_fr']

    if not translations:
        print("No translated entries found! "
              "Expected files matching '*_translated.json' with 'translation_fr' fields.")
        return

    # Apply translations by walking through messages in order
    global_idx = 0
    applied = 0
    for context in root.findall('context'):
        for message in context.findall('message'):
            if global_idx in translations:
                trans_elem = message.find('translation')
                if trans_elem is not None:
                    trans_elem.text = translations[global_idx]
                    if 'type' in trans_elem.attrib:
                        del trans_elem.attrib['type']
                    applied += 1
            global_idx += 1

    # Write with proper formatting
    ET.indent(tree, space='    ')
    tree.write(output_file, encoding='utf-8', xml_declaration=True)

    # Fix: restore DOCTYPE and use double quotes in XML declaration
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace(
        "<?xml version='1.0' encoding='utf-8'?>",
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>'
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Applied {applied} of {len(translations)} translations to '{output_file}'")
    print(f"Remaining unfinished: {1410 - applied} (approx)")


def show_stats(ts_file: str) -> None:
    """Show translation statistics for a .ts file."""
    tree = ET.parse(ts_file)
    root = tree.getroot()

    total = 0
    finished = 0
    unfinished = 0
    contexts = set()

    for context in root.findall('context'):
        ctx_name = context.find('name').text or ''
        contexts.add(ctx_name)
        for message in context.findall('message'):
            total += 1
            trans = message.find('translation')
            if trans is not None:
                if trans.get('type') == 'unfinished':
                    unfinished += 1
                elif trans.text and trans.text.strip():
                    finished += 1
                else:
                    unfinished += 1

    print(f"File: {ts_file}")
    print(f"  Contexts: {len(contexts)}")
    print(f"  Total messages: {total}")
    print(f"  Finished: {finished}")
    print(f"  Unfinished: {unfinished}")
    print(f"  Coverage: {finished / total * 100:.1f}%" if total > 0 else "  Coverage: 0%")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Qt .ts Translation Helper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest='command')

    # Extract command
    extract_parser = subparsers.add_parser(
        'extract', help='Extract unfinished translations into JSON chunks')
    extract_parser.add_argument('ts_file', help='Input .ts file')
    extract_parser.add_argument(
        '--reference', '-r', help='Reference .ts file (e.g., German) for context')
    extract_parser.add_argument(
        '--output-dir', '-o', default='fr_chunks', help='Output directory for chunks')
    extract_parser.add_argument(
        '--chunk-size', '-c', type=int, default=100, help='Entries per chunk (default: 100)')

    # Merge command
    merge_parser = subparsers.add_parser(
        'merge', help='Merge translated chunks back into .ts file')
    merge_parser.add_argument('ts_file', help='Original .ts file')
    merge_parser.add_argument('translations_dir', help='Directory with *_translated.json files')
    merge_parser.add_argument('output_file', help='Output .ts file path')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show translation statistics')
    stats_parser.add_argument('ts_file', help='Input .ts file')

    args = parser.parse_args()

    if args.command == 'extract':
        extract_entries(args.ts_file, args.reference, args.output_dir, args.chunk_size)
    elif args.command == 'merge':
        merge_translations(args.ts_file, args.translations_dir, args.output_file)
    elif args.command == 'stats':
        show_stats(args.ts_file)
    else:
        parser.print_help()
