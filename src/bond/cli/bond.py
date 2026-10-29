import re
import sys
from argparse import ArgumentParser, Namespace

from returns.result import Failure

from bond.endpoints.voices import find_voice, list_all
from bond.runtime import BondRuntime


def list_toolsets(_: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic()
    toolsets = runtime.list_toolsets()
    if not toolsets:
        print(f"No toolsets found")
        return
    print("Toolsets:\n  " + "\n  ".join(toolsets))


def list_voices(args: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(enable_plugins=False)
    provider = runtime.get_provider(args.provider)
    voices_endpoint = provider.voices()
    assert voices_endpoint is not None
    matching_voices = list(
        voice
        for voice in list_all(voices_endpoint)
        if args.name is None or re.search(args.name, voice.name) is not None
    )
    limited_voices = matching_voices[: args.limit]
    print(f"Listing {len(limited_voices)} of {len(matching_voices)} voices:")
    print("  " + "\n  ".join(f"{voice.name}: {voice.id}" for voice in limited_voices))


def list_providers(_: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic()
    providers = runtime.list_providers()
    if len(providers) == 0:
        print("No providers configured")
        return
    print("Providers:\n  " + "\n  ".join(providers))


def list_personas(_: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic()
    personas = runtime.list_personas()
    if len(personas) == 0:
        print("No personas configured")
        return
    print("Personas:\n  " + "\n  ".join(personas))


def validate_personas(_: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic()
    personas = runtime.list_personas()
    if len(personas) == 0:
        print("No personas configured")
        return
    errors: list[tuple[str, str]] = []
    for name in personas:
        result = runtime.get_persona(name)
        if isinstance(result, Failure):
            errors.append((name, f"Failed to load config: {result.failure()}"))
            continue
        config = result.unwrap()
        try:
            persona = config.instantiate(runtime)
            persona.release()
        except Exception as e:
            errors.append((name, f"Failed to instantiate: {e}"))
            continue
        print(f"  ✓ {name}")
    if errors:
        print(f"\n{len(errors)} of {len(personas)} persona(s) have problems:")
        for name, error in errors:
            print(f"  ✗ {name}: {error}")
        return 1
    print(f"\nAll {len(personas)} persona(s) validated successfully")
    return 0


def list_plugins(_: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic(enable_plugins=False)
    plugins = runtime.list_plugins()
    if len(plugins) == 0:
        print("No plugins found")
        return
    print("Plugins:\n  " + "\n  ".join(plugins))


def tts(args: Namespace):
    runtime = BondRuntime.get_instance()
    runtime.initialize_dynamic()
    provider = runtime.get_provider(args.provider)
    voices = provider.voices()
    if voices is None:
        print("This provider does not support voices")
        return
    tts = provider.tts_endpoint()
    if tts is None:
        print("This provider does not support tts")
        return
    voice = find_voice(voices, args.voice)
    if voice is None:
        print(f"Could not find voice: {args.voice}")
        return
    audio = tts.tts(args.model, voice.id, args.text, {})
    audio.play()


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    plugins_parser = subparsers.add_parser("plugins")
    plugins_parser.set_defaults(callback=list_plugins)

    voices_parser = subparsers.add_parser("voices")
    voices_parser.add_argument("provider", type=str)
    voices_parser.add_argument("--limit", "-l", type=int)
    voices_parser.add_argument("--offset", "-o", type=int, default=0)
    voices_parser.add_argument("--name", "-n", type=str)
    voices_parser.set_defaults(callback=list_voices)

    providers_parser = subparsers.add_parser("providers")
    providers_parser.set_defaults(callback=list_providers)

    personas_parser = subparsers.add_parser("personas")
    personas_parser.set_defaults(callback=list_personas)

    validate_personas_parser = subparsers.add_parser(
        "validate-personas",
        help="Validate all persona configs by loading and instantiating them",
    )
    validate_personas_parser.set_defaults(callback=validate_personas)

    toolsets_parser = subparsers.add_parser("toolsets")
    toolsets_parser.set_defaults(callback=list_toolsets)

    tts_parser = subparsers.add_parser("tts")
    tts_parser.add_argument("provider", type=str)
    tts_parser.add_argument("model", type=str)
    tts_parser.add_argument("voice", type=str)
    tts_parser.add_argument("text", type=str)
    tts_parser.set_defaults(callback=tts)

    args = parser.parse_args()
    if not hasattr(args, "callback"):
        print("Missing command")
        return 1
    result = args.callback(args)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
