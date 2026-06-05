"""
Postgres-backed implementation of the Anthropic memory tool.

The memory tool models a small filesystem rooted at ``/memories``. We persist each
file as a row in the ``ai_memories`` table keyed by its full path; directories are
implicit (derived from the path prefixes of the files that exist). These functions
back the (disabled) ``memory`` ai_function in :mod:`.aikani`, which dispatches the
server-side tool calls to them.

https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#tool-commands
"""

import datetime
import posixpath

from sqlalchemy import select

from calypso import db, models

MEMORY_ROOT = "/memories"
MAX_LINES = 999_999


# ==== helpers ====
def _validate_path(path: str) -> str:
    """Resolve *path* to its canonical form and ensure it stays within ``/memories``."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Error: A path is required.")
    if "\\" in path or "\x00" in path or "%2e" in path.lower():
        raise ValueError(f"Error: Invalid path {path}. Paths must be within {MEMORY_ROOT}.")
    normalized = posixpath.normpath(path)
    if normalized != MEMORY_ROOT and not normalized.startswith(MEMORY_ROOT + "/"):
        raise ValueError(f"Error: Invalid path {path}. Paths must be within {MEMORY_ROOT}.")
    return normalized


def _is_hidden(path: str) -> bool:
    """Whether any component of the path (relative to root) is hidden or node_modules."""
    rel = path[len(MEMORY_ROOT) + 1 :]
    return any(part.startswith(".") or part == "node_modules" for part in rel.split("/") if part)


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("", "K", "M", "G", "T"):
        if size < 1024 or unit == "T":
            return f"{int(size)}" if unit == "" else f"{size:.1f}{unit}"
        size /= 1024


def _number_lines(content: str, start: int = 1) -> str:
    lines = content.split("\n")
    return "\n".join(f"{i:>6}\t{line}" for i, line in enumerate(lines, start=start))


async def _get_file(session, path: str) -> models.AIMemory | None:
    return await session.get(models.AIMemory, path)


async def _children(session, path: str) -> list[models.AIMemory]:
    """All files anywhere beneath the directory *path*."""
    prefix = path + "/"
    result = await session.execute(select(models.AIMemory).where(models.AIMemory.path.startswith(prefix)))
    return list(result.scalars())


# ==== commands ====
async def memory_view(path: str, start: int | None = None, end: int | None = None) -> str:
    path = _validate_path(path)
    async with db.async_session() as session:
        file = await _get_file(session, path)
        if file is not None:
            return _view_file(path, file.content, start, end)

        # not a file -- treat as a directory
        children = [f for f in await _children(session, path) if not _is_hidden(f.path)]
        if not children and path != MEMORY_ROOT:
            return f"Error: The path {path} does not exist. Please provide a valid path."
        return _view_directory(path, children)


def _view_file(path: str, content: str, start: int | None, end: int | None) -> str:
    lines = content.split("\n")
    if len(lines) > MAX_LINES:
        return f"File {path} exceeds maximum line limit of {MAX_LINES:,} lines."

    offset = 1
    if start is not None:
        n = len(lines)
        offset = max(start, 1)
        last = n if (end is None or end == -1 or end > n) else end
        lines = lines[offset - 1 : last]

    body = _number_lines("\n".join(lines), start=offset)
    return f"Here's the content of {path} with line numbers:\n{body}"


def _view_directory(path: str, children: list[models.AIMemory]) -> str:
    prefix = path + "/"
    sizes = {f.path: len(f.content.encode("utf-8")) for f in children}

    # collect entries up to 2 levels deep, aggregating directory sizes
    entries: dict[str, int] = {path: sum(sizes.values())}
    for fpath, size in sizes.items():
        parts = fpath[len(prefix) :].split("/")
        lvl1 = prefix + parts[0]
        if len(parts) == 1:
            entries[lvl1] = size
        else:
            entries[lvl1] = entries.get(lvl1, 0) + size
            lvl2 = lvl1 + "/" + parts[1]
            entries[lvl2] = entries.get(lvl2, 0) + size

    listing = "\n".join(f"{_human_size(entries[p])}\t{p}" for p in sorted(entries))
    return (
        f"Here're the files and directories up to 2 levels deep in {path}, "
        f"excluding hidden items and node_modules:\n{listing}"
    )


async def memory_create(path: str, file_text: str) -> str:
    path = _validate_path(path)
    if path == MEMORY_ROOT:
        return f"Error: {path} is a directory, not a file."
    async with db.async_session() as session:
        if await _get_file(session, path) is not None:
            return f"Error: File {path} already exists"
        # guard against shadowing an existing implicit directory
        if await _children(session, path):
            return f"Error: {path} is a directory, not a file."
        session.add(models.AIMemory(path=path, content=file_text))
        await session.commit()
    return f"File created successfully at: {path}"


async def memory_str_replace(path: str, old_str: str, new_str: str) -> str:
    path = _validate_path(path)
    async with db.async_session() as session:
        file = await _get_file(session, path)
        if file is None:
            return f"Error: The path {path} does not exist. Please provide a valid path."

        content = file.content
        occurrences = content.count(old_str)
        if occurrences == 0:
            return f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}."
        if occurrences > 1:
            # report the (1-indexed) line numbers where old_str begins
            lines_with = [
                str(i) for i, line in enumerate(content.split("\n"), start=1) if old_str.split("\n")[0] in line
            ]
            return (
                f"No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines: "
                f"{', '.join(lines_with)}. Please ensure it is unique"
            )

        new_content = content.replace(old_str, new_str)
        file.content = new_content
        file.timestamp = datetime.datetime.utcnow()
        await session.commit()

    snippet = _edit_snippet(new_content, content.index(old_str), new_str)
    return f"The memory file has been edited.\n{snippet}"


def _edit_snippet(new_content: str, char_offset: int, new_str: str, context: int = 4) -> str:
    """A few lines of context around an edit, with line numbers."""
    lines = new_content.split("\n")
    edit_start = new_content[:char_offset].count("\n") + 1
    edit_end = edit_start + new_str.count("\n")
    start = max(edit_start - context, 1)
    end = min(edit_end + context, len(lines))
    return _number_lines("\n".join(lines[start - 1 : end]), start=start)


async def memory_insert(path: str, insert_line: int, insert_text: str) -> str:
    path = _validate_path(path)
    async with db.async_session() as session:
        file = await _get_file(session, path)
        if file is None:
            return f"Error: The path {path} does not exist"

        lines = file.content.split("\n")
        if insert_line < 0 or insert_line > len(lines):
            return (
                f"Error: Invalid `insert_line` parameter: {insert_line}. "
                f"It should be within the range of lines of the file: [0, {len(lines)}]"
            )

        lines[insert_line:insert_line] = insert_text.split("\n")
        file.content = "\n".join(lines)
        file.timestamp = datetime.datetime.utcnow()
        await session.commit()
    return f"The file {path} has been edited."


async def memory_delete(path: str) -> str:
    path = _validate_path(path)
    async with db.async_session() as session:
        file = await _get_file(session, path)
        if file is not None:
            await session.delete(file)
            await session.commit()
            return f"Successfully deleted {path}"

        # directory: delete recursively
        children = await _children(session, path)
        if not children and path != MEMORY_ROOT:
            return f"Error: The path {path} does not exist"
        for child in children:
            await session.delete(child)
        await session.commit()
    return f"Successfully deleted {path}"


async def memory_rename(old_path: str, new_path: str) -> str:
    old_path = _validate_path(old_path)
    new_path = _validate_path(new_path)
    async with db.async_session() as session:
        file = await _get_file(session, old_path)
        if file is not None:
            if await _get_file(session, new_path) is not None or await _children(session, new_path):
                return f"Error: The destination {new_path} already exists"
            file.path = new_path
            file.timestamp = datetime.datetime.utcnow()
            await session.commit()
            return f"Successfully renamed {old_path} to {new_path}"

        # directory: move every descendant
        children = await _children(session, old_path)
        if not children:
            return f"Error: The path {old_path} does not exist"
        if await _get_file(session, new_path) is not None or await _children(session, new_path):
            return f"Error: The destination {new_path} already exists"
        for child in children:
            child.path = new_path + child.path[len(old_path) :]
            child.timestamp = datetime.datetime.utcnow()
        await session.commit()
    return f"Successfully renamed {old_path} to {new_path}"
