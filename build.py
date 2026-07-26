#!/usr/bin/env python3
"""Build tui-cv outputs from config.json.

Usage:
    python3 build.py tui [md] [pdf]
    python3 build.py --check

Targets are explicit: ``tui`` writes index.html, ``md`` writes the configured
CV Markdown output, and ``pdf`` writes the configured print-ready PDF.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
import shutil
import subprocess
import sys
from html import escape, unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config.json"
TUI_TEMPLATE = HERE / "template-TUI.html"
CV_TEMPLATE = HERE / "template-CV.html"
TUI_OUTPUT = HERE / "index.html"
PRINT_HTML = HERE / ".cv-print.html"
VALID_TARGETS = ("tui", "md", "pdf")
VALID_THEMES = ("dark", "light")
TUI_SECTION_NAMES = (
    "profile", "experience", "education", "skills", "compensation",
    "certifications", "honours", "contact",
)
TUI_COMMAND_SECTION_REQUIREMENTS = {
    "experience": ("experience",),
    "education": ("education",),
    "skills": ("skills",),
    "compensation": ("compensation",),
    "certifications": ("certifications",),
    "contact": ("contact",),
    "whoami": ("profile",),
    "portfolio": ("profile", "honours"),
}
PDF_SECTION_NAMES = (
    "pdf.header", "profile", "experience", "skills", "certifications", "education",
    "honours", "compensation", "contact", "pdf.footer",
)
MD_SECTION_NAMES = (
    "md.header", "profile", "experience", "skills", "education",
    "certifications", "honours", "compensation", "contact", "md.footer",
)
TUI_TEMPLATE_PLACEHOLDERS = ("%%TITLE%%", "%%DESCRIPTION%%", "%%FAVICON_TEXT%%", "%%THEME%%", "%%CONFIG_JSON%%")
PDF_TEMPLATE_PLACEHOLDERS = ("%%CV_HEADER%%", "%%CV_HERO%%", "%%CV_LAYOUT%%", "%%CV_FOOTER%%")
# The publisher-owned template has moved to the four placeholders above. Keep
# these substitutions temporarily so this exporter also works with an already
# generated/checked-out legacy template while rejecting every other token.
LEGACY_PDF_TEMPLATE_PLACEHOLDERS = (
    "%%CV_PAGE_TITLE%%", "%%CV_CONTACT_NOTE_COLOR%%", "%%CV_FONT_SIZE_PROFILE%%", "%%CV_FONT_SIZE_EXPERIENCE%%", "%%CV_FONT_SIZE_SIDEBAR%%",
)
REQUIRED_KEYS = [
    "meta", "theme", "sidebar", "banner", "boot", "composer", "statusbar",
    "modal", "messages", "commands", "profile", "experience", "education",
    "skills", "compensation", "certifications", "honours", "contact",
    "outputs",
]
CSS_UNIT_RE = re.compile(r"^(0*\.[0-9]+|[1-9][0-9]*(?:\.[0-9]+)?)(?:px|pt|em|rem|%)$")
DEFAULT_PDF_PROFILE_FONT_SIZE = "8.9px"
SAFE_BASENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser",
]


def esc_attr(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def esc(value: object) -> str:
    return escape(str(value), quote=True)


def safe_basename(value: object, path: str, errors: list[str]) -> None:
    """Validate a filename stem so outputs cannot write outside this project."""
    if not isinstance(value, str) or not value or not SAFE_BASENAME_RE.fullmatch(value):
        errors.append(f"{path} must be a non-empty safe base filename")
    # Dotted project stems (for example, ``D.A.Ferreira``) are valid. Reject
    # only the generated output extensions, which prevents accidental doubles.
    elif (value in {".", ".."} or Path(value).name != value or "/" in value or "\\" in value
          or value.lower().endswith((".pdf", ".md"))):
        errors.append(f"{path} must be a safe base filename without a path or extension")


def validate_sections(value: object, path: str, allowed: tuple[str, ...], errors: list[str]) -> None:
    """Ensure an output section selection is an ordered, duplicate-free list."""
    if not isinstance(value, list) or not all(isinstance(section, str) for section in value):
        errors.append(f"{path} must be an array of section names")
        return
    duplicates = sorted({section for section in value if value.count(section) > 1})
    if duplicates:
        errors.append(f"{path} must not contain duplicate section names: {', '.join(duplicates)}")
    unsupported = [section for section in value if section not in allowed]
    if unsupported:
        errors.append(f"{path} has unsupported section names: {', '.join(dict.fromkeys(unsupported))} (allowed: {', '.join(allowed)})")


def validate_role_content(content: object, path: str, errors: list[str], required: bool = True) -> None:
    if not isinstance(content, dict):
        errors.append(f"{path} must be an object")
        return
    if (required or "description" in content) and not isinstance(content.get("description"), str):
        errors.append(f"{path}.description must be a string")
    points = content.get("points")
    if (required or "points" in content) and (not isinstance(points, list) or not all(isinstance(p, str) for p in points)):
        errors.append(f"{path}.points must be an array of strings")
    overrides = content.get("overrides", {})
    if not isinstance(overrides, dict):
        errors.append(f"{path}.overrides must be an object")
        return
    for target, override in overrides.items():
        override_path = f"{path}.overrides.{target}"
        if not isinstance(target, str) or not isinstance(override, dict):
            errors.append(f"{path}.overrides entries must be target objects")
            continue
        unsupported = sorted(set(override) - {"description", "points"})
        if unsupported:
            errors.append(f"{override_path} has unsupported fields: {', '.join(unsupported)} (allowed: description, points)")
        validate_role_content({**override, "overrides": {}}, override_path, errors, required=False)


def validate(cfg: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(cfg, dict):
        return ["top-level config must be an object"]
    missing = [key for key in REQUIRED_KEYS if key not in cfg]
    if missing:
        return [f"missing top-level keys: {', '.join(missing)}"]

    meta, theme, banner = cfg["meta"], cfg["theme"], cfg["banner"]
    if not isinstance(meta, dict) or not isinstance(theme, dict) or not isinstance(banner, dict):
        return ["meta, theme, and banner must be objects"]
    for key in ("title", "description"):
        if not meta.get(key): errors.append(f"meta.{key} is required")
    if theme.get("default") not in VALID_THEMES: errors.append(f"theme.default must be one of {list(VALID_THEMES)}")
    if "{theme}" not in theme.get("switchedText", ""): errors.append("theme.switchedText must contain the {theme} placeholder")
    if len(banner.get("dim", [])) != len(banner.get("accent", [])): errors.append("banner.dim and banner.accent must have the same number of lines")

    legacy_keys = sorted({"cv", "exports"} & set(cfg))
    if legacy_keys:
        errors.append(f"legacy top-level keys are not supported: {', '.join(legacy_keys)}; use outputs")

    outputs = cfg["outputs"]
    if not isinstance(outputs, dict) or set(outputs) != {"tui", "pdf", "md"}:
        errors.append("outputs must contain exactly tui, pdf, and md objects")
    else:
        tui, pdf, markdown = outputs["tui"], outputs["pdf"], outputs["md"]
        if not isinstance(tui, dict) or set(tui) != {"sections"}:
            errors.append("outputs.tui must contain exactly sections")
        else:
            validate_sections(tui["sections"], "outputs.tui.sections", TUI_SECTION_NAMES, errors)
        if not isinstance(pdf, dict) or set(pdf) != {"filename", "header", "footer", "fontSizes", "skillsLimit", "sections"}:
            errors.append("outputs.pdf must contain exactly filename, header, footer, fontSizes, skillsLimit, and sections")
        else:
            safe_basename(pdf["filename"], "outputs.pdf.filename", errors)
            for key in ("header", "footer"):
                if not isinstance(pdf[key], str): errors.append(f"outputs.pdf.{key} must be a string")
            if isinstance(pdf["skillsLimit"], bool) or not isinstance(pdf["skillsLimit"], int) or pdf["skillsLimit"] < 0:
                errors.append("outputs.pdf.skillsLimit must be a non-negative integer")
            sizes = pdf["fontSizes"]
            if not isinstance(sizes, dict) or not {"experience", "sidebar"}.issubset(sizes) or set(sizes) - {"profile", "experience", "sidebar"}:
                errors.append("outputs.pdf.fontSizes must contain experience and sidebar, with optional profile")
            else:
                for key, value in sizes.items():
                    match = CSS_UNIT_RE.fullmatch(value) if isinstance(value, str) else None
                    if not match or float(match.group(1)) <= 0: errors.append(f"outputs.pdf.fontSizes.{key} must be a positive size with an explicit safe unit")
            validate_sections(pdf["sections"], "outputs.pdf.sections", PDF_SECTION_NAMES, errors)
        if not isinstance(markdown, dict) or set(markdown) != {"filename", "enabled", "header", "footer", "sections"}:
            errors.append("outputs.md must contain exactly filename, enabled, header, footer, and sections")
        else:
            safe_basename(markdown["filename"], "outputs.md.filename", errors)
            if not isinstance(markdown["enabled"], bool): errors.append("outputs.md.enabled must be a boolean")
            for key in ("header", "footer"):
                if not isinstance(markdown[key], str): errors.append(f"outputs.md.{key} must be a string")
            validate_sections(markdown["sections"], "outputs.md.sections", MD_SECTION_NAMES, errors)

    compensation = cfg["compensation"]
    if not isinstance(compensation, dict): errors.append("compensation must be an object")
    else:
        for key in ("title", "description", "url", "linkText"):
            if not isinstance(compensation.get(key), str): errors.append(f"compensation.{key} must be a string")

    experience = cfg["experience"]
    if not isinstance(experience, list): errors.append("experience must be an array")
    else:
        for job_index, job in enumerate(experience):
            roles = job.get("roles") if isinstance(job, dict) else None
            if not isinstance(roles, list):
                errors.append(f"experience[{job_index}].roles must be an array")
                continue
            for role_index, role in enumerate(roles):
                validate_role_content(role.get("content") if isinstance(role, dict) else None,
                                      f"experience[{job_index}].roles[{role_index}].content", errors)

    commands = cfg["commands"]
    if not isinstance(commands, list): errors.append("commands must be an array")
    else:
        names = set()
        for i, command in enumerate(commands):
            if not isinstance(command, dict): errors.append(f"commands[{i}] must be an object"); continue
            name = command.get("name", "")
            if not name.startswith("/"): errors.append(f"commands[{i}].name must start with '/'")
            if name in names: errors.append(f"duplicate command name {name}")
            names.add(name)
            if not command.get("type"): errors.append(f"commands[{i}] ({name}) needs a 'type'")
            if command.get("type") == "link":
                href = command.get("href", "")
                if not href: errors.append(f"commands[{i}] ({name}) is a link and needs 'href'")
                elif (not href.startswith(("http", "/")) and not (HERE / href).exists()
                       and href not in {f'{cfg["outputs"]["pdf"]["filename"]}.pdf', f'{cfg["outputs"]["md"]["filename"]}.md'}):
                    errors.append(f"commands[{i}] ({name}): local link target '{href}' not found in {HERE}")

    modal = cfg["modal"]
    if not isinstance(modal, dict) or sum(bool(m.get("active")) for m in modal.get("models", []) if isinstance(m, dict)) != 1:
        errors.append('modal.models needs exactly one entry with "active": true')
    sidebar = cfg["sidebar"]
    avatar = sidebar.get("avatar", "") if isinstance(sidebar, dict) else ""
    if avatar and not avatar.startswith("http") and not (HERE / avatar).exists(): errors.append(f"sidebar.avatar '{avatar}' not found in {HERE}")
    return errors


def resolve_content(content: dict, target: str) -> dict:
    override = content.get("overrides", {}).get(target, {})
    return {field: override.get(field, content[field]) for field in ("description", "points")}


def tui_command_enabled(command: dict, selected_sections: set[str]) -> bool:
    """Mirror the TUI command dependency map before config reaches the browser."""
    return all(section in selected_sections for section in TUI_COMMAND_SECTION_REQUIREMENTS.get(command.get("type"), ()))


def build_tui_config(cfg: dict) -> dict:
    """Return an isolated TUI payload containing only selected CV content."""
    payload = deepcopy(cfg)
    selected_sections = set(payload["outputs"]["tui"]["sections"])
    for section in TUI_SECTION_NAMES:
        if section not in selected_sections:
            payload.pop(section, None)
    payload["commands"] = [
        command for command in payload["commands"]
        if tui_command_enabled(command, selected_sections)
    ]
    return payload


def validate_tui_config(cfg: dict, payload: dict) -> None:
    """Defend the build boundary: excluded TUI data must not be injected."""
    selected_sections = set(cfg["outputs"]["tui"]["sections"])
    excluded_content = set(TUI_SECTION_NAMES) - selected_sections
    leaked_content = sorted(excluded_content & set(payload))
    if leaked_content:
        raise ValueError(f"TUI config error: unselected content was injected: {', '.join(leaked_content)}")
    leaked_commands = [
        command.get("name", "<unnamed>") for command in payload["commands"]
        if not tui_command_enabled(command, selected_sections)
    ]
    if leaked_commands:
        raise ValueError(f"TUI config error: commands need excluded sections: {', '.join(leaked_commands)}")


def build_tui(cfg: dict) -> str:
    tui_cfg = build_tui_config(cfg)
    validate_tui_config(cfg, tui_cfg)
    template = TUI_TEMPLATE.read_text(encoding="utf-8")
    # The sidebar avatar remains shell chrome. Its only direct profile lookup
    # must be inert when the profile payload was deliberately removed.
    if "profile" not in tui_cfg:
        profile_alt = 'alt="${esc(CONFIG.profile.name)}"'
        if profile_alt not in template:
            raise ValueError("template error: missing safe sidebar-avatar profile alternative")
        template = template.replace(profile_alt, 'alt=""')
    blob = json.dumps(tui_cfg, ensure_ascii=False, indent=2).replace("</", "<\\/")
    html = (template.replace("%%TITLE%%", esc_attr(tui_cfg["meta"]["title"]))
            .replace("%%DESCRIPTION%%", esc_attr(tui_cfg["meta"]["description"]))
            .replace("%%FAVICON_TEXT%%", esc_attr(tui_cfg["meta"].get("faviconText", "od")))
            .replace("%%THEME%%", esc_attr(tui_cfg["theme"]["default"]))
            .replace("%%CONFIG_JSON%%", blob))
    leftover = [p for p in TUI_TEMPLATE_PLACEHOLDERS if p in html]
    if leftover: raise ValueError(f"template error: unreplaced placeholders: {leftover}")
    return html


def safe_url(value: object) -> str | None:
    url = unescape(str(value).strip())
    if not url or any(ord(char) < 32 for char in url): return None
    if url.lower().startswith(("http://", "https://")):
        return esc(url) if re.match(r"https?://[^/?#]+", url, re.IGNORECASE) else None
    if url.lower().startswith("mailto:"): return esc(url) if len(url[7:]) else None
    return esc(url) if not re.match(r"^[a-z][a-z0-9+.-]*:", url, re.IGNORECASE) and not url.startswith(("/", "\\")) else None


def link(url: object, text: str) -> str:
    href = safe_url(url)
    return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{text}</a>' if href else text


def md_html(value: object) -> str:
    """Render safe inline Markdown for the print HTML only."""
    text, protected = escape(str(value), quote=True).replace("\r\n", "\n").replace("\r", "\n"), []
    def protect(html: str) -> str: protected.append(html); return f"\x00{len(protected)-1}\x00"
    def inline(text_value: str) -> str:
        text_value = re.sub(r"`([^`\n]+)`", lambda m: protect(f"<code>{m.group(1)}</code>"), text_value)
        text_value = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"<strong>\2</strong>", text_value)
        text_value = re.sub(r"(?<!\*)\*(?![\s*])(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", text_value)
        return re.sub(r"(?<!\w)_(?![\s_])(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text_value)
    def render(match: re.Match[str]) -> str:
        label, url = match.groups(); rendered = inline(label); href = safe_url(unescape(url))
        return protect(f'<a href="{href}" target="_blank" rel="noopener noreferrer">{rendered}</a>') if href else rendered
    text = inline(re.sub(r"\[([^\]\n]+)\]\(([^()\s]*(?:\([^()\s]*\)[^()\s]*)*)\)", render, text)).replace("\n", "<br>")
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)


def render_experience(cfg: dict) -> str:
    jobs = []
    for job in cfg["experience"]:
        roles = []
        for role in job["roles"]:
            content = resolve_content(role["content"], "cv")
            points = "".join(f"<li>{md_html(point)}</li>" for point in content["points"])
            roles.append(f'<article class="role"><div class="role-head"><h4>{esc(role["title"])}</h4><time>{esc(role["period"])}</time></div><p>{md_html(content["description"])}</p>' + (f"<ul>{points}</ul>" if points else "") + "</article>")
        jobs.append(f'<section class="job"><div class="job-head"><h3>{esc(job["company"])}</h3><span>{esc(job["period"])}</span></div><div class="job-place">{esc(job["location"])}</div>{"".join(roles)}</section>')
    return "".join(jobs)


def render_skills(cfg: dict, limit: int) -> str:
    return "".join(f'<article class="signal"><div class="signal-index">{index:02d}</div><div><b>{esc(skill["k"])}</b><div class="chips">{"".join(f"<span>{esc(tag)}</span>" for tag in skill.get("tags", [])[:4])}</div></div></article>' for index, skill in enumerate(cfg["skills"][:limit], 1))


def render_education(cfg: dict) -> str:
    return "".join(f'<div class="mini"><b>{link(edu["url"], esc(edu["degree"])) if edu.get("url") else esc(edu["degree"])}</b><span>{esc(edu["school"])} · {esc(edu["location"])} · {esc(edu["period"])}</span><p>{md_html(edu["detail"])}</p></div>' for edu in cfg["education"])


def render_certifications(cfg: dict) -> str:
    return "".join(f'<div class="mini"><b>{link(cert["url"], esc(cert["name"]))}</b><span>{esc(cert["since"])}</span></div>' for cert in cfg["certifications"])


def render_honours(cfg: dict, limit: int) -> str:
    return "".join(f'<div class="mini"><b>{md_html(honour["t"])}</b><p>{md_html(honour["d"])}</p></div>' for honour in cfg["honours"][:limit])


def render_pdf_hero(cfg: dict) -> str:
    """Render the complete CV hero only when the profile section is selected."""
    profile, contact = cfg["profile"], cfg["contact"]
    email = esc(contact["email"])
    avatar = f'<img class="avatar" src="{esc(cfg["sidebar"]["avatar"])}" alt="{esc(profile["name"])}">' if cfg["sidebar"].get("avatar") else ""
    metrics = "".join(
        f'<div class="metric"><b>{esc(metric["v"])}</b><span>{esc(metric["l"])}</span></div>'
        for metric in profile["metrics"]
    )
    return (f'<section class="hero"><div><h1><a href="mailto:{email}" target="_blank" rel="noopener noreferrer">{esc(profile["name"])}</a></h1>'
            f'<p class="title">{esc(profile["title"])}</p><p class="summary">{md_html(profile["summary"])}</p>'
            f'<div class="metrics">{metrics}</div></div>{avatar}</section>')


def render_pdf_compensation(cfg: dict) -> str:
    compensation = cfg["compensation"]
    href = safe_url(compensation["url"]) if compensation["url"] and compensation["linkText"] else None
    description = f'<p>{md_html(compensation["description"])}</p>' if compensation["description"] else ""
    linked = (f'<p class="compensation-link"><a href="{href}" target="_blank" rel="noopener noreferrer">'
              f'{md_html(compensation["linkText"])}</a></p>') if href else ""
    return f'<section class="rail-box compensation"><h2>{esc(compensation["title"])}</h2>{description}{linked}</section>'


def pdf_note_color(cfg: dict) -> str:
    note_color = str(cfg["contact"].get("noteColor") or "#e5c07b")
    if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", note_color):
        raise ValueError("config error: contact.noteColor must be a hex color string")
    return note_color


def render_pdf_contact(cfg: dict) -> str:
    contact = cfg["contact"]
    note = f'<p class="contact-note">{md_html(contact["note"])}</p>' if contact.get("note") else ""
    details = (
        f'{link("mailto:" + contact["email"], esc(contact["email"]))}'
        f'{link(contact["linkedin"], esc(contact["linkedin"].replace("https://www.", "")))}'
        f'{link(contact["github"], esc(contact["github"].replace("https://", "")))}'
        f'<span>{esc(contact["location"])} · {esc(contact["citizenship"])} · {esc(contact["languages"])}</span>{note}'
    )
    return f'<section class="rail-box"><h2>Contact</h2><div class="contact">{details}</div></section>'


def render_pdf_html(cfg: dict, skills_limit: int, honours_limit: int) -> str:
    html = CV_TEMPLATE.read_text(encoding="utf-8")
    found = re.findall(r"%%CV_[A-Z0-9_]+%%", html)
    required = set(PDF_TEMPLATE_PLACEHOLDERS)
    permitted = required | set(LEGACY_PDF_TEMPLATE_PLACEHOLDERS)
    if (not required.issubset(found) or set(found) - permitted
            or any(found.count(placeholder) != 1 for placeholder in set(found))):
        raise ValueError(f"template error: CV placeholders must include exactly one of each required token {list(PDF_TEMPLATE_PLACEHOLDERS)} and no unknown tokens; found {found}")

    pdf = cfg["outputs"]["pdf"]
    selected = set(pdf["sections"])
    note_color = pdf_note_color(cfg)
    header = f'<p class="foot">{md_html(pdf["header"])}</p>' if "pdf.header" in selected and pdf["header"] else ""
    footer = f'<p class="foot">{md_html(pdf["footer"])}</p>' if "pdf.footer" in selected and pdf["footer"] else ""
    hero = render_pdf_hero(cfg) if "profile" in selected else ""
    main = f'<section class="experience"><h2>Experience</h2>{render_experience(cfg)}</section>' if "experience" in selected else ""
    rail_renderers = {
        "skills": lambda: f'<section class="rail-box"><h2>Skills</h2>{render_skills(cfg, skills_limit)}</section>',
        "certifications": lambda: f'<section class="rail-box"><h2>Certifications</h2>{render_certifications(cfg)}</section>',
        "education": lambda: f'<section class="rail-box"><h2>Education</h2>{render_education(cfg)}</section>',
        "honours": lambda: f'<section class="rail-box"><h2>Honours</h2>{render_honours(cfg, honours_limit)}</section>',
        "compensation": lambda: render_pdf_compensation(cfg),
        "contact": lambda: render_pdf_contact(cfg),
    }
    rail = "".join(rail_renderers[section]() for section in pdf["sections"] if section in rail_renderers)
    if main or rail:
        layout_class = " main-only" if main and not rail else " rail-only" if rail and not main else ""
        rail_html = f'<aside class="rail">{rail}</aside>' if rail else ""
        layout = f'<div class="layout{layout_class}">{main}{rail_html}</div>'
    else:
        layout = ""
    replacements = {
        "%%CV_HEADER%%": header,
        "%%CV_HERO%%": hero,
        "%%CV_LAYOUT%%": layout,
        "%%CV_FOOTER%%": footer,
        "%%CV_PAGE_TITLE%%": esc(f'{cfg["profile"]["name"]} - CV'),
        "%%CV_CONTACT_NOTE_COLOR%%": note_color,
        "%%CV_FONT_SIZE_PROFILE%%": pdf["fontSizes"].get("profile", DEFAULT_PDF_PROFILE_FONT_SIZE),
        "%%CV_FONT_SIZE_EXPERIENCE%%": pdf["fontSizes"]["experience"],
        "%%CV_FONT_SIZE_SIDEBAR%%": pdf["fontSizes"]["sidebar"],
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    leftover = re.findall(r"%%CV_[A-Z0-9_]+%%", html)
    if leftover: raise ValueError(f"template error: unreplaced placeholders: {sorted(set(leftover))}")
    return html


def markdown_link(label: str, url: object) -> str:
    return f"[{label}]({url})" if safe_url(url) else label


def build_markdown(cfg: dict) -> str:
    """Build selected source-Markdown sections; source prose remains verbatim."""
    profile, contact = cfg["profile"], cfg["contact"]

    def profile_section() -> str:
        lines = [f'# {profile["name"]}', "", profile["title"], "", profile["summary"], "", "## Profile metrics", ""]
        lines += [f'- **{metric["v"]}** — {metric["l"]}' for metric in profile["metrics"]]
        return "\n".join(lines)

    def experience_section() -> str:
        lines = ["## Experience", ""]
        for job in cfg["experience"]:
            lines += [f'### {job["company"]} — {job["location"]}', f'*{job["period"]}*', ""]
            for role in job["roles"]:
                content = resolve_content(role["content"], "cv")
                lines += [f'#### {role["title"]}', f'*{role["period"]}*', "", content["description"], ""]
                lines += [f"- {point}" for point in content["points"]] + [""]
        return "\n".join(lines).rstrip()

    def skills_section() -> str:
        lines = ["## Skills", ""]
        for skill in cfg["skills"]:
            tags = f' ({", ".join(skill.get("tags", []))})' if skill.get("tags") else ""
            lines.append(f'- **{skill["k"]}**{tags}: {skill.get("s", "")}')
        return "\n".join(lines)

    def education_section() -> str:
        lines = ["## Education", ""]
        for edu in cfg["education"]:
            lines += [f'- **{markdown_link(edu["degree"], edu.get("url", ""))}** — {edu["school"]}, {edu["location"]} ({edu["period"]})  ', f'  {edu["detail"]}']
        return "\n".join(lines)

    def certifications_section() -> str:
        lines = ["## Certifications", ""]
        lines += [f'- **{markdown_link(cert["name"], cert["url"])}** — {cert["since"]}' for cert in cfg["certifications"]]
        return "\n".join(lines)

    def honours_section() -> str:
        lines = ["## Honours", ""]
        lines += [f'- **{honour["t"]}** — {honour["d"]}' for honour in cfg["honours"]]
        return "\n".join(lines)

    def compensation_section() -> str:
        compensation = cfg["compensation"]
        lines = ["## Compensation", "", f'### {compensation["title"]}', "", compensation["description"]]
        if compensation["url"] and compensation["linkText"]:
            lines += ["", markdown_link(compensation["linkText"], compensation["url"])]
        return "\n".join(lines)

    def contact_section() -> str:
        lines = ["## Contact", "", f'- Email: [{contact["email"]}](mailto:{contact["email"]})', f'- LinkedIn: {markdown_link(contact["linkedin"], contact["linkedin"])}', f'- GitHub: {markdown_link(contact["github"], contact["github"])}', f'- Location: {contact["location"]}', f'- Citizenship: {contact["citizenship"]}', f'- Languages: {contact["languages"]}']
        if contact.get("note"):
            lines += ["", contact["note"]]
        return "\n".join(lines)

    renderers = {
        "md.header": lambda: cfg["outputs"]["md"]["header"],
        "profile": profile_section,
        "experience": experience_section,
        "skills": skills_section,
        "education": education_section,
        "certifications": certifications_section,
        "honours": honours_section,
        "compensation": compensation_section,
        "contact": contact_section,
        "md.footer": lambda: f'---\n\n{cfg["outputs"]["md"]["footer"]}' if cfg["outputs"]["md"]["footer"] else "",
    }
    blocks = [renderers[section]() for section in cfg["outputs"]["md"]["sections"]]
    return "\n\n".join(block for block in blocks if block).rstrip() + "\n"


def find_chrome(explicit: str | None) -> str:
    for candidate in [explicit] if explicit else CHROME_CANDIDATES:
        if candidate and (Path(candidate).exists() or shutil.which(candidate)): return candidate
    raise ValueError("error: Google Chrome/Chromium not found — pass --chrome /path/to/chrome")


def count_pdf_pages(pdf_path: Path) -> int:
    return max(len(re.findall(rb"/Type\s*/Page\b(?!s)", pdf_path.read_bytes())), 1)


def build_pdf(cfg: dict, args: argparse.Namespace) -> None:
    chrome, output = find_chrome(args.chrome), HERE / f'{cfg["outputs"]["pdf"]["filename"]}.pdf'
    PRINT_HTML.write_text(render_pdf_html(cfg, args.skills, args.honours), encoding="utf-8")
    result = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={output}", PRINT_HTML.as_uri()], capture_output=True, text=True, timeout=120)
    if not args.keep_html: PRINT_HTML.unlink(missing_ok=True)
    if result.returncode != 0 or not output.exists(): raise ValueError(f"error: chrome pdf export failed\n{result.stderr[-2000:]}")
    pages = count_pdf_pages(output)
    print(f"wrote {output} ({output.stat().st_size / 1024:.0f} KB, {pages} page{'s' if pages != 1 else ''})")
    if pages > args.max_pages: raise ValueError(f"error: PDF has {pages} pages, max allowed is {args.max_pages} — trim content in config.json or lower --skills/--honours")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", choices=VALID_TARGETS, help="outputs to build")
    parser.add_argument("--check", action="store_true", help="validate config.json only; write nothing")
    parser.add_argument("--chrome", help="path to Chrome/Chromium (pdf target only)")
    parser.add_argument("--keep-html", action="store_true", help="keep .cv-print.html (pdf target only)")
    parser.add_argument("--max-pages", type=int, default=None, help="maximum PDF pages (default: 1; pdf target only)")
    parser.add_argument("--skills", type=int, default=None, help="PDF skill domains (default: outputs.pdf.skillsLimit; pdf target only)")
    parser.add_argument("--honours", type=int, default=None, help="PDF honours (default: 4; pdf target only)")
    args = parser.parse_args()
    if not args.check and not args.targets: parser.error("specify at least one target: tui, md, or pdf")
    pdf_options = (args.chrome, args.keep_html, args.max_pages, args.skills, args.honours)
    if any(value is not None and value is not False for value in pdf_options) and "pdf" not in args.targets and not args.check:
        parser.error("PDF options require the pdf target")
    if len(set(args.targets)) != len(args.targets): parser.error("each target may be specified only once")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    errors = validate(cfg)
    if errors:
        for error in errors: print(f"config error: {error}", file=sys.stderr)
        sys.exit(1)
    if args.check:
        print("config.json OK — validation only; no files written")
        return
    if "md" in args.targets and not cfg["outputs"]["md"]["enabled"]: parser.error("the md target is disabled by outputs.md.enabled")
    args.max_pages = 1 if args.max_pages is None else args.max_pages
    args.skills = cfg["outputs"]["pdf"]["skillsLimit"] if args.skills is None else args.skills
    args.honours = 4 if args.honours is None else args.honours
    if args.max_pages < 1 or args.skills < 0 or args.honours < 0: parser.error("--max-pages must be at least 1; --skills and --honours cannot be negative")
    if "tui" in args.targets:
        html = build_tui(cfg); TUI_OUTPUT.write_text(html, encoding="utf-8"); print(f"wrote {TUI_OUTPUT} ({len(html):,} bytes) from {CONFIG.name} + {TUI_TEMPLATE.name}")
    if "md" in args.targets:
        output = HERE / f'{cfg["outputs"]["md"]["filename"]}.md'; content = build_markdown(cfg); output.write_text(content, encoding="utf-8"); print(f"wrote {output} ({len(content):,} bytes) from {CONFIG.name}")
    if "pdf" in args.targets: build_pdf(cfg, args)


if __name__ == "__main__":
    main()
