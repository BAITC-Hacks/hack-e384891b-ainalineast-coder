"""Document display labels and source-grounded structural references."""
import re

_EXTENSIONS = re.compile(r"(?:\.(?:md|markdown|docx?|pdf|xlsx?|txt|csv|tsv))+$", re.I)
_TYPES = {"раздел": "раздела", "глава": "главы", "статья": "статьи"}

def display_name(name):
    """Remove transport suffixes without shortening the actual document title."""
    value = str(name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    value = _EXTENSIONS.sub("", value).replace("_", " ").strip()
    return re.sub(r"\s+", " ", value) or "Документ"

def _clean_heading(text):
    return re.sub(r"^#{1,6}\s*", "", str(text).replace("**", "").replace("\\.", ".")).strip()

def _heading(text, allow_number=False):
    value = _clean_heading(text)
    explicit = re.match(r"^(раздел|глава|статья)\s+([0-9]+(?:\.[0-9]+)*|[IVXLCDM]+)\b[.\s:–—-]*(.*)$", value, re.I)
    if explicit:
        kind, number, title = explicit.groups()
        return {"type": kind.lower(), "number": number, "title": title.strip()}
    number = re.match(r"^(\d+)\.\s+(.+)$", value)
    if allow_number and number and len(number.group(2)) < 180:
        return {"type": "раздел", "number": number.group(1), "title": number.group(2).strip()}
    return None

def _descriptor(part, genitive=False):
    label = _TYPES[part["type"]] if genitive else part["type"]
    title = str(part.get("title", "")).strip().strip("«»")
    return label + " " + str(part["number"]) + (" «" + title + "»" if title else "")

def citation(clause):
    """Use explicit metadata; never reinterpret 5.3.2 as an article hierarchy."""
    if not clause:
        return ""
    if clause.get("citation"):
        return str(clause["citation"])
    ref = str(clause.get("ref", "")).strip()
    structure = clause.get("structure") or []
    own_heading = clause.get("structuralHeading")
    if own_heading:
        return _descriptor(own_heading)
    letter = re.fullmatch(r"(\d+(?:\.\d+)*)\.([а-яa-z])", ref, re.I)
    bullet = re.match(r"^(\d+(?:\.\d+)*)\s*(?:· список|\.список-)\s*(\d+)$", ref)
    if letter:
        label = "подпункт «" + letter.group(2) + "» пункта " + letter.group(1)
    elif bullet:
        label = "ненумерованный элемент перечня пункта " + bullet.group(1)
    elif re.fullmatch(r"\d+(?:\.\d+)*", ref):
        label = "пункт " + ref
    else:
        ordinal = clause.get("order")
        ordinal = ordinal + 1 if isinstance(ordinal, int) else clause.get("line")
        if ordinal is None:
            match = re.search(r"(\d+)$", ref)
            ordinal = match.group(1) if match else None
        label = "ненумерованный абзац" + (" " + str(ordinal) if ordinal is not None else "")
    if not structure:
        section = _heading(clause.get("section", ""), allow_number=True)
        if section and (not re.match(r"^\d", ref) or ref.split(".")[0] == section["number"]):
            structure = [section]
    # The source order gives nesting. Inner structures appear first in a reference.
    if structure:
        label += " " + " ".join(_descriptor(part, True) for part in reversed(structure))
    return label

def structural_headings(raw):
    """Find explicit headings and numbered headings supported by source formatting."""
    source = raw.splitlines()
    headings = {}
    for i, raw_line in enumerate(source, 1):
        clean = _clean_heading(raw_line)
        marked = bool(re.match(r"^\s*(?:\*\*|#{1,6}\s)", raw_line))
        number = re.match(r"^(\d+)\.\s+(.+)$", clean)
        following_child = bool(number and re.search(r"(?m)^\s*" + re.escape(number.group(1)) + r"\.\d", "\n".join(source[i:])))
        allow_number = bool(number and not number.group(2).endswith((".", ";", ":")) and (marked or following_child))
        item = _heading(clean, allow_number)
        if item and not re.search(r"\.{2,}\s*\d+\s*$", clean):
            headings[i] = item
    return headings

def add_citations(clauses, raw):
    """Collect real headings, then attach context at each extracted source location."""
    headings = structural_headings(raw)
    source = raw.splitlines()
    active = []
    cursor = 0
    rank = {"раздел": 1, "глава": 2, "статья": 3}
    for clause in clauses:
        target = int(clause.get("line", cursor + 1))
        for lineno in range(cursor + 1, target + 1):
            if _clean_heading(source[lineno-1]).casefold() in ("оглавление", "содержание", "приложения"):
                active = []
            if lineno in headings:
                part = headings[lineno]
                active = [p for p in active if rank[p["type"]] < rank[part["type"]]]
                active.append(part)
        cursor = max(cursor, target)
        clause["structure"] = [dict(part) for part in active]
        if target in headings:
            clause["structuralHeading"] = dict(headings[target])
        # An unknown numbered section must not be supplied by the legacy parser.
        clause["citation"] = citation({**clause, "section": ""})
    return clauses
