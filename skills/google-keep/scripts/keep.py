#!/usr/bin/env python3
"""Deterministic Google Keep CRUD through agent-browser.

Agents call this script. They do not write a new browser script.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import re
import time
from pathlib import Path

HOME = "https://keep.google.com/u/0/"
SESSION = os.environ.get("KEEP_SESSION", "keep")
VIEWS = ("notes", "reminders", "archive", "trash")
VIEW_TABS = {"notes": "Notes", "reminders": "Reminders", "archive": "Archive", "trash": "Trash"}
SKIP_TABS = {"Notes", "Reminders", "Archive", "Trash", "Edit Labels"}
TYPES = ("Reminders", "Lists", "Images", "Recordings", "Drawings", "URLs")

CARD_JS = r"""
(() => {
  const cards = [...document.querySelectorAll(".IZ65Hb-n0tgWb")];
  const out = [];
  const seen = new Set();
  for (const [index, card] of cards.entries()) {
    const r = card.getBoundingClientRect();
    if (r.width < 180 || r.width > 1400 || r.height < 24) continue;
    const raw = (card.innerText || "").replace(/\u00a0/g, " ").replace(/\u202f/g, " ");
    const lines = raw.split(/\n+/).map(s => s.trim()).filter(Boolean);
    const edited = (lines.find(s => s.startsWith("Edited ")) || "");
    const body = lines.filter(s => s !== "Close" && s !== "Take a note…" && s !== "PINNED" && s !== "OTHERS" && !s.startsWith("Edited "));
    if (!body.length) continue;
    const title = body[0];
    const text = body.slice(1).join("\n").slice(0, 4000);
    const key = String(index);
    card.setAttribute("data-keep-token", key);
    if (seen.has(key)) continue;
    seen.add(key);
    const links = [...new Set([...card.querySelectorAll("a[href]")].map(a => a.href).filter(h => h && !h.startsWith("javascript:")))].slice(0, 8);
    out.push({
      token: key,
      y: Math.round(r.y + window.scrollY),
      h: Math.round(r.height),
      pinned: !!card.querySelector('[aria-label="Unpin"]'),
      edited,
      title,
      text,
      links
    });
  }
  out.sort((a, b) => a.y - b.y);
  return JSON.stringify(out);
})()
"""

FIELDS_JS = r"""
(() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0 || r.bottom <= 0 || r.top >= innerHeight) return false;
    const hit = document.elementFromPoint(Math.max(0,r.left)+Math.min(10,r.width/2),Math.max(0,r.top)+Math.min(10,r.height/2));
    return !!hit && (el === hit || el.contains(hit));
  };
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), text: el.children.length && [...el.children].every(n => n.tagName === "P") ? [...el.children].map(n => n.innerText === "\n" ? "" : n.innerText).join("\n") : (el.innerText === "\n" ? "" : (el.innerText || ""))};
  };
  const title = [...document.querySelectorAll('[contenteditable="true"]')].findLast(el => vis(el) && (el.getAttribute("aria-label") === "Title" || el.getAttribute("role") === "textbox"));
  const body = [...document.querySelectorAll('div[role="combobox"]')].findLast(vis);
  const take = [...document.querySelectorAll('div[role="combobox"]')].filter(vis).sort((a, b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y)[0];
  const close = [...document.querySelectorAll('[role="button"]')].filter(el => vis(el) && (el.innerText || "").trim() === "Close").at(-1);
  return JSON.stringify({
    url: location.href,
    title: title ? box(title) : null,
    body: body ? box(body) : null,
    take: take ? box(take) : null,
    close: close ? box(close) : null
  });
})()
"""


class KeepError(Exception):
    pass


def chrome_path() -> str:
    env = os.environ.get("KEEP_CHROME")
    if env:
        return env
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    program = os.environ.get("PROGRAMFILES", "")
    program_x86 = os.environ.get("PROGRAMFILES(X86)", "")
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        Path("/opt/google/chrome/google-chrome"),
        Path("/opt/google/chrome/chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/google-chrome"),
        Path(program) / "Google/Chrome/Application/chrome.exe" if program else None,
        Path(program_x86) / "Google/Chrome/Application/chrome.exe" if program_x86 else None,
        Path(local) / "Google/Chrome/Application/chrome.exe" if local else None,
    ]
    for path in candidates:
        if path and path.is_file():
            return str(path)
    for name in ("google-chrome-stable", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise KeepError("Google Chrome was not found. Install it, or set KEEP_CHROME to the Chrome binary.")


def chrome_user_data() -> Path | None:
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    candidates = [
        home / "Library/Application Support/Google/Chrome",
        Path(xdg) / "google-chrome" if xdg else home / ".config/google-chrome",
        Path(local) / "Google/Chrome/User Data" if local else None,
    ]
    for path in candidates:
        if path and (path / "Local State").is_file():
            return path
    return None


def profile_dir() -> str:
    env = os.environ.get("KEEP_PROFILE")
    if env:
        return env
    user_data = chrome_user_data()
    if user_data:
        data = json.loads((user_data / "Local State").read_text(encoding="utf-8"))
        last = data.get("profile", {}).get("last_used")
        if last:
            return last
    raise KeepError("Set KEEP_PROFILE to a Chrome profile directory. `agent-browser profiles` lists them.")


def browser_bin() -> str:
    found = shutil.which("agent-browser")
    if not found:
        raise KeepError("agent-browser is not on PATH. Install it, then rerun this script.")
    return found


def select_all() -> str:
    return "Meta+a" if sys.platform == "darwin" else "Control+a"


def parse_jsonish(value):
    for _ in range(3):
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return value
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


def run(args: list[str], stdin: str | None = None) -> str:
    cmd = [
        browser_bin(),
        "--session", SESSION,
        "--executable-path", chrome_path(),
        "--profile", profile_dir(),
        *args,
    ]
    try:
        proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise KeepError("Browser command timed out. A write may have completed; inspect the note before retrying.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise KeepError(detail[-2000:] or f"agent-browser failed: {args[0]}")
    return proc.stdout


def batch(cmds: list[list[str]]) -> list:
    payload = run(["batch", "--bail", "--json"], stdin=json.dumps(cmds))
    items = json.loads(payload)
    evals = []
    for item in items:
        if not item.get("success", True):
            raise KeepError(str(item.get("error") or item)[:2000])
        res = item.get("result") or {}
        if item.get("command", [""])[0] == "eval" and isinstance(res, dict) and "result" in res:
            evals.append(parse_jsonish(res["result"]))
    return evals


def eval_js(js: str):
    return batch([["eval", js]])[0]


def current_url() -> str:
    try:
        out = run(["get", "url"])
    except KeepError:
        return ""
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("http") or line.startswith("about:"):
            return line
    return ""


def ensure() -> None:
    url = current_url()
    if "keep.google.com" not in url:
        run(["open", HOME])
        run(["wait", "1500"])
        url = current_url()
    if "accounts.google.com" in url:
        raise KeepError(
            "Keep opened a Google sign-in page. Use the system Chrome binary and a profile directory that is already signed in."
        )


def scroll_top() -> None:
    eval_js(
        '(() => { window.scrollTo(0,0); const s = document.querySelector(".PvRhvb-bN97Pc"); if (s) s.scrollTop = 0; return JSON.stringify({ok:true}); })()'
    )


def ensure_list_view() -> None:
    mode = eval_js(
        '(() => JSON.stringify(document.querySelector(\'[aria-label="List view"]\') ? "grid" : "list"))()'
    )
    if mode == "grid":
        run(["click", '[aria-label="List view"]'])
        run(["wait", "500"])


def wait_ready(note: str | None = None) -> None:
    run(["wait", "1500"])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = eval_js("""JSON.stringify({url:location.href,ready:document.readyState,
          title:!!document.querySelector('[aria-label="Title"][contenteditable="true"]'),
          cards:document.querySelectorAll('.IZ65Hb-n0tgWb').length,
          empty:/0 search results|Notes you add appear here|No matching results|No results|No notes|Your archived notes|No notes in Trash/i.test(document.body.innerText),
          busy:!!document.querySelector('[role="progressbar"]')})""")
        if "accounts.google.com" in state['url']:
            raise KeepError("Sign in to Keep in Chrome before using this skill.")
        if state['ready'] == 'complete' and not state['busy']:
            if note and note_id(state['url']) == note and fields().get('title') and fields().get('close'):
                return
            if not note and (state['cards'] > 1 or state['empty']):
                return
        run(['wait', '300'])
    raise KeepError("Keep did not become ready within 30 seconds. Inspect state before retrying a write.")


def goto_home() -> None:
    ensure()
    if fields().get("close"):
        close_composer()
    click_tab("Notes")
    wait_ready()
    scroll_top()


def apply_query(query: str) -> None:
    js = (
        "(() => { location.assign("
        + json.dumps(HOME)
        + " + '#search/text=' + encodeURIComponent("
        + json.dumps(query)
        + ")); return JSON.stringify({ok:true}); })()"
    )
    eval_js(js)
    wait_ready()


def click_tab(label: str) -> None:
    run(['click', '[role="tab"][aria-label=' + json.dumps(label) + ']'])
    run(['wait', '500'])


def apply_type(name: str) -> None:
    if name not in TYPES:
        raise KeepError(f"Unknown type {name!r}. Choose from {', '.join(TYPES)}.")
    run(["click", '[aria-label="Search"]'])
    run(["wait", "400"])
    js = (
        "(() => { const want = "
        + json.dumps(name)
        + "; const el = [...document.querySelectorAll('div,button,span')].find(node => (node.innerText || '').trim() === want && node.childElementCount === 0 && node.getBoundingClientRect().width > 0);"
        + " if (!el) return JSON.stringify({ok:false}); const r = el.getBoundingClientRect();"
        + " return JSON.stringify({ok:true, x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}); })()"
    )
    hit = eval_js(js)
    if not hit.get("ok"):
        raise KeepError(f"Search chip {name!r} was not visible.")
    mouse(hit["x"], hit["y"])
    run(["wait", "800"])


def read_card(token: str) -> dict:
    selector = '[data-keep-token=' + json.dumps(token) + ']'
    run(['scrollintoview', selector])
    run(['click', selector])
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        data = read_open()
        if data['id']:
            close_composer()
            return data
        run(['wait', '200'])
    raise KeepError("Card did not resolve to a note ID.")


def collect() -> list[dict]:
    notes = eval_js(CARD_JS)
    if not isinstance(notes, list):
        raise KeepError(f"Card read failed: {notes!r}"[:500])
    return notes


def mouse(x: int, y: int, wait_ms: str = "400") -> None:
    batch([
        ["mouse", "move", str(x), str(y)],
        ["mouse", "down", "left"],
        ["mouse", "up", "left"],
        ["wait", wait_ms],
    ])


def type_at(x: int, y: int, text: str, replace: bool) -> None:
    cmds = [
        ["mouse", "move", str(x), str(y)],
        ["mouse", "down", "left"],
        ["mouse", "up", "left"],
        ["wait", "200"],
    ]
    if replace:
        cmds.append(["press", select_all()])
    if text == "":
        cmds.append(["press", "Backspace"])
    else:
        cmds.append(["keyboard", "inserttext", text])
    batch(cmds)


def fields() -> dict:
    data = eval_js(FIELDS_JS)
    if not isinstance(data, dict):
        raise KeepError("Could not read the open note.")
    return data


def note_id(url: str) -> str:
    marker = "#NOTE/"
    if marker not in url:
        return ""
    return url.split(marker, 1)[1].split("&", 1)[0].split("?", 1)[0]


def open_note(note: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", note):
        raise KeepError("Invalid note ID.")
    run(["open", HOME + "#NOTE/" + note])
    wait_ready(note)
    if read_open()["id"] != note:
        raise KeepError("The requested note did not open.")


def close_composer() -> None:
    data = fields()
    close = data.get("close")
    if not close:
        raise KeepError("The Close button was not visible.")
    mouse(close["x"], close["y"], "700")


def open_composer() -> dict:
    goto_home()
    ensure_list_view()
    data = fields()
    if not data.get("title"):
        take = data.get("take")
        if not take:
            raise KeepError("The Take a note field was not visible.")
        mouse(take["x"], take["y"], "400")
        data = fields()
    if not data.get("title") or not data.get("body"):
        raise KeepError("The note composer did not open.")
    return data


def read_open() -> dict:
    data = fields()
    url = data.get("url") or current_url()
    return {
        "id": note_id(url),
        "url": url,
        "title": (data.get("title") or {}).get("text", ""),
        "body": (data.get("body") or {}).get("text", ""),
    }


def cmd_list(args: argparse.Namespace) -> dict:
    if args.limit < 1:
        raise KeepError("--limit must be positive.")
    chosen = [args.label, args.type, None if args.view == "notes" else args.view]
    if sum(bool(value) for value in chosen) > 1:
        raise KeepError("Use one of --label, --type, or a nondefault --view per call.")
    if args.query and any(chosen):
        raise KeepError("Combine repeated --query values with each other only. Run label, type, or view as a separate command.")
    goto_home()
    ensure_list_view()
    if args.view != "notes":
        click_tab(VIEW_TABS[args.view])
    elif args.label:
        click_tab(args.label)
    elif args.type:
        apply_type(args.type)

    if args.query:
        found: list[dict] = []
        seen = set()
        for query in args.query:
            apply_query(query)
            ensure_list_view()
            for note in collect():
                opened = read_card(note.pop("token"))
                note.update(id=opened['id'], title=opened['title'], text=opened['body'])
                key = note['id']
                if key in seen:
                    continue
                seen.add(key)
                note["matchedQuery"] = query
                found.append(note)
        notes = found
    else:
        notes = collect()
        if not args.all and args.view == "notes":
            notes = [note for note in notes if not note.get("pinned")]
    notes = notes[:args.limit]
    for note in notes:
        if 'token' in note:
            opened = read_card(note.pop('token'))
            note.update(id=opened['id'], title=opened['title'], text=opened['body'])
    return {"ok": True, "count": len(notes), "notes": notes}


def cmd_filters(_: argparse.Namespace) -> dict:
    ensure()
    tabs = eval_js(
        '(() => JSON.stringify([...document.querySelectorAll(\'[role=tab]\')].map(el => (el.getAttribute("aria-label") || el.innerText || "").trim()).filter(Boolean)))()'
    )
    if not isinstance(tabs, list):
        raise KeepError("Could not read Keep labels.")
    labels = []
    for tab in tabs:
        if tab not in labels and tab not in SKIP_TABS:
            labels.append(tab)
    return {"ok": True, "views": list(VIEWS), "labels": labels, "types": list(TYPES)}


def cmd_get(args: argparse.Namespace) -> dict:
    open_note(args.note)
    return {"ok": True, "note": read_open()}


def cmd_create(args: argparse.Namespace) -> dict:
    if not args.title and not args.body:
        raise KeepError("Pass a nonempty --title or --body.")
    query = args.title or args.body.splitlines()[0]
    search = argparse.Namespace(query=[query], label=None, type=None, view="notes", limit=10000, all=True)
    before = {n['id'] for n in cmd_list(search)['notes']}
    data = open_composer()
    if args.title:
        type_at(data['title']['x'], data['title']['y'], args.title, replace=False)
    if args.body:
        body = fields()['body']
        type_at(body['x'], body['y'], args.body, replace=False)
    close_composer()
    after = cmd_list(search)['notes']
    created = [n for n in after if n['id'] not in before and n['title'] == args.title and n['text'] == args.body]
    if len(created) != 1:
        raise KeepError("Note may have been saved, but its new ID could not be resolved. Inspect list before retrying creation.")
    open_note(created[0]['id'])
    return {"ok": True, "note": read_open()}


def cmd_update(args: argparse.Namespace) -> dict:
    if args.title is None and args.body is None:
        raise KeepError("Pass --title or --body.")
    target = args.note
    open_note(target)
    data = fields()
    if args.title is not None:
        if not data.get("title"):
            raise KeepError("The title field was not visible.")
        type_at(data["title"]["x"], data["title"]["y"], args.title, replace=True)
    if args.body is not None:
        data = fields()
        if not data.get("body"):
            raise KeepError("The body field was not visible.")
        type_at(data["body"]["x"], data["body"]["y"], args.body, replace=True)
    close_composer()
    open_note(target)
    return {"ok": True, "note": read_open()}


def menu_click(label: str) -> None:
    js = (
        "(() => { const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };"
        + " const items = [...document.querySelectorAll('[role=menuitem]')].filter(vis);"
        + " const item = items.find(el => (el.innerText || '').trim() === "
        + json.dumps(label)
        + "); if (!item) return JSON.stringify({ok:false, labels:items.map(el => (el.innerText || '').trim())});"
        + " const r = item.getBoundingClientRect(); return JSON.stringify({ok:true, x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}); })()"
    )
    hit = eval_js(js)
    for _ in range(5):
        if hit.get("ok"):
            break
        run(["wait", "300"])
        hit = eval_js(js)
    if not hit.get("ok"):
        raise KeepError(f"Menu item {label!r} was not visible. Saw {hit.get('labels')}.")
    mouse(hit["x"], hit["y"], "500")


def cmd_delete(args: argparse.Namespace) -> dict:
    target = args.note
    open_note(target)
    if not args.forever and eval_js('JSON.stringify(document.body.innerText.includes("Note in Trash"))'):
        return {"ok": True, "id": target, "trashed": True, "forever": False}
    data = fields()
    root_js = r"""
(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const body = [...document.querySelectorAll('div[role="combobox"]')].findLast(vis);
  if (!body) return JSON.stringify({ok:false, step:"body"});
  let root = body;
  for (let i = 0; i < 14 && root.parentElement; i++) {
    root = root.parentElement;
    if ([...root.querySelectorAll('[role=button]')].some(el => vis(el) && (el.innerText || "").trim() === "Close")) break;
  }
  const more = [...root.querySelectorAll('[aria-label="More"]')].filter(vis).sort((a, b) => b.getBoundingClientRect().y - a.getBoundingClientRect().y)[0];
  if (!more) return JSON.stringify({ok:false, step:"more"});
  document.querySelectorAll("[data-keep-more]").forEach(e=>e.removeAttribute("data-keep-more"));
  more.setAttribute("data-keep-more","true");
  more.scrollIntoView({block:"center"});
  const r = more.getBoundingClientRect();
  return JSON.stringify({ok:true, x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)});
})()
"""
    if not data.get("body"):
        open_note(target)
    more = eval_js(root_js)
    if not more.get("ok"):
        raise KeepError(f"Could not find More on the open note ({more}).")
    run(["click", '[data-keep-more="true"]'])
    run(["wait", "500"])
    menu_click("Delete note")
    result = {"ok": True, "id": target, "trashed": True, "forever": False}
    if not args.forever:
        return result
    open_note(target)
    forever = eval_js(
        r"""
(() => {
  const buttons = [...document.querySelectorAll('[aria-label="Delete forever"]')].filter(el => el.getBoundingClientRect().width > 0).map(el => {
    const r = el.getBoundingClientRect();
    let blob = "";
    let n = el;
    for (let i = 0; i < 10 && n; i++, n = n.parentElement) {
      const t = (n.innerText || "").replace(/\s+/g, " ").trim();
      if (t.includes("Note in Trash") && t.length < 400) { blob = t.slice(0, 240); break; }
    }
    return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), blob};
  });
  const hit = buttons.find(b => b.blob.includes("Note in Trash"));
  return JSON.stringify(hit ? {ok:true, x:hit.x, y:hit.y} : {ok:false, buttons});
})()
"""
    )
    if not forever.get("ok"):
        raise KeepError("Delete forever was not on this trashed note.")
    mouse(forever["x"], forever["y"], "400")
    confirm = eval_js(
        r"""
(() => {
  const dialog = [...document.querySelectorAll("[role=dialog], [role=alertdialog]")].find(el => /forever/i.test(el.innerText || ""));
  if (!dialog) return JSON.stringify({ok:false, step:"dialog"});
  const btn = [...dialog.querySelectorAll("button, [role=button]")].find(el => (el.innerText || "").trim() === "Delete" && el.getBoundingClientRect().width > 0);
  if (!btn) return JSON.stringify({ok:false, step:"confirm"});
  const r = btn.getBoundingClientRect();
  return JSON.stringify({ok:true, x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)});
})()
"""
    )
    if not confirm.get("ok"):
        raise KeepError(f"The Delete forever confirmation did not appear ({confirm}).")
    mouse(confirm["x"], confirm["y"], "800")
    result["forever"] = True
    return result


def cmd_close(_: argparse.Namespace) -> dict:
    run(["close"])
    return {"ok": True, "closed": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google Keep CRUD via the signed-in Chrome profile.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    listed = sub.add_parser("list", help="List notes, or union repeated --query searches.")
    listed.add_argument("--query", action="append", default=[], help="Keep search text. Repeat to union searches.")
    listed.add_argument("--label", help="Exact sidebar label.")
    listed.add_argument("--view", choices=VIEWS, default="notes")
    listed.add_argument("--type", choices=TYPES)
    listed.add_argument("--limit", type=int, default=50)
    listed.add_argument("--all", action="store_true", help="Include pinned notes when not searching.")
    listed.set_defaults(func=cmd_list)

    filters = sub.add_parser("filters", help="List views, labels, and type chips.")
    filters.set_defaults(func=cmd_filters)

    get = sub.add_parser("get", help="Open one note by ID.")
    get.add_argument("note")
    get.set_defaults(func=cmd_get)

    create = sub.add_parser("create", help="Create a note and return its id.")
    create.add_argument("--title", default="")
    create.add_argument("--body", default="")
    create.set_defaults(func=cmd_create)

    update = sub.add_parser("update", help="Replace a note title or body.")
    update.add_argument("note")
    update.add_argument("--title")
    update.add_argument("--body")
    update.set_defaults(func=cmd_update)

    delete = sub.add_parser("delete", help="Move a note to Trash. --forever removes it.")
    delete.add_argument("note")
    delete.add_argument("--forever", action="store_true")
    delete.set_defaults(func=cmd_delete)

    close = sub.add_parser("close", help="Close the headless Keep session.")
    close.set_defaults(func=cmd_close)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        emit(args.func(args))
    except (KeepError, OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)}, code=1)


def emit(obj: dict, code: int = 0) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
