def command_requires_streaming(proto, cmd_name: str) -> bool:
    cmd_def = proto.commands.get(cmd_name, {})
    return bool(cmd_def.get("requires_streaming", False))
