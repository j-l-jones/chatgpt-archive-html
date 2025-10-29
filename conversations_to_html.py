#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export conversations JSON to readable HTML pages (one per conversation) plus an index.html.
- Renders only conversation content (user/assistant by default; can include system/tool).
- Embeds images and referenced files.

Usage:
  python conversations_to_html.py conversations.json --user-name "Foo" --assistant-name "Chat Friend"  --out-dir site_out
"""

import glob
from html import escape as html_escape
import json
import markdown
from optparse import OptionParser
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple
import unicodedata



class ChatLogToHtml():

    def __init__(self, user_name, assistant_name):
        self.title_keys = ["title", "conversation_title", "headline", "name"] # ??
        self.root_list_keys = ("conversations", "items", "data", "threads") # ??
        self.message_keys = ("messages", "msgs", "entries") # ??

        self.role_map = {
            "user": user_name,
            "assistant": assistant_name,
            "system": "System",
            "tool": "Tool",
            "developer": "Developer",
            "function": "Function",
            "unknown": "Message",
        }

    def get_base_css(self):
        base_css = """
        :root { --bg:#0b0c10; --fg:#f0f3f6; --muted:#a3b3c2; --accent:#9ae6b4; --chip:#20232a; --card:#111318; }
        * { box-sizing: border-box; }
        html, body { margin:0; padding:0; background:var(--bg); color:var(--fg); font: 16px/1.55 system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji; }
        a { color: #8ab4ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .container { max-width: 980px; margin: 0 auto; padding: 28px 16px 80px; }
        .header { display:flex; gap:12px; align-items:center; margin-bottom: 24px; }
        .header h1 { font-size: 24px; margin:0; }
        .title { font-size: 28px; margin: 12px 0 20px; }
        .message { background: var(--card); border:1px solid #252a33; border-radius: 14px; padding: 14px 16px; margin: 12px 0; }
        .role { font-weight:600; color: var(--accent); margin-bottom: 8px; }
        .msg-body p { margin: .6em 0; }
        .msg-body pre { background: #0a0c12; border: 1px solid #232a33; padding: 12px; overflow-x: auto; border-radius: 10px; }
        .msg-body code { background: #0a0c12; padding: 0 .25em; border-radius: 6px; }
        .attachments { margin-top: 8px; color: var(--muted); font-size: 0.95em; }
        .attachments ul { margin: .4em 0 .2em 1.2em; }
        .image-grid { display:grid; grid-template-columns: repeat(auto-fill,minmax(160px,1fr)); gap:10px; margin-top:8px; }
        .image-grid img { width:100%; height:auto; border-radius: 10px; background:#0a0c12; border:1px solid #232a33; }
        hr.sep { border:0; border-top:1px solid #242933; margin: 16px 0; }
        .search { margin: 12px 0 20px; display:flex; gap:10px; }
        .search input { flex:1; padding:10px 12px; border-radius: 10px; border:1px solid #2a2f3a; background:#0f1116; color:var(--fg); }
        .index-list { display:grid; gap:12px; }
        .card { background: var(--card); border:1px solid #252a33; border-radius: 14px; padding: 10px 12px; }
        .card h3 { margin: 0 0 8px; font-size: 18px; }
        .small { color: var(--muted); font-size: .9em; }
        """
        return base_css

    def get_index_html(self):
        index_html = """<!doctype html>
        <html lang="en">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{site_title}</title>
        <style>{css}</style>
        </head>
        <body>
        <div class="container">
          <div class="header">
            <h1>{site_title}</h1>
          </div>
          <div class="search">
            <input id="q" type="search" placeholder="Search conversations by title…" oninput="filter()">
          </div>
          <div id="list" class="index-list">
            {items}
          </div>
        </div>
        <script>
        function filter() {{
          const q = document.getElementById('q').value.toLowerCase();
          const items = document.querySelectorAll('.card');
          items.forEach(it => {{
            const t = it.getAttribute('data-title');
            it.style.display = t.includes(q) ? '' : 'none';
          }});
        }}
        </script>
        </body>
        </html>
        """
        return index_html

    def get_page_html(self):
        page_html = """<!doctype html>
        <html lang="en">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{title}</title>
        <style>{css}</style>
        </head>
        <body>
        <div class="container">
          <div class="header">
            <a href="index.html">← Back</a>
            <h1 class="title">{title}</h1>
          </div>
          {body}
        </div>
        </body>
        </html>
        """
        return page_html

    def load_conversations(self, in_file: Path, out_dir: Path) -> List[Dict[str, Any]]:
        with in_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise Exception(f"Unexpected format for {in_file}")
        return data

    def generate_html(self, convs, out_dir):
        index_items = []
        for i, conv in enumerate(convs):
            title = self.get_title(conv, i)
            fname = self.canonicalize(title) + ".html"
            out_path = self.create_unique_path(out_dir / fname)

            msgs = self.find_messages(conv, out_dir) or []
            body_parts = []
            for m in msgs:
                label = self.get_role(m)
                html = self.message_to_html(m, label)
                body_parts.append(html)

            page_html = self.get_page_html()
            base_css = self.get_base_css()
            html = page_html.format(title=html_escape(title), css=base_css, body="\n".join(body_parts))
            out_path.write_text(html, encoding="utf-8")
            index_items.append((title, out_path.name))

        index_html = self.build_index(index_items)
        (out_dir / "index.html").write_text(index_html, encoding="utf-8")

        print(f"Wrote {len(index_items)} pages to {out_dir.resolve()} (open index.html)")

    def get_title(self, conv: Dict[str, Any], idx: int) -> str:
        for k in self.title_keys:
            v = conv.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        meta = conv.get("meta") or conv.get("metadata") or {}
        if isinstance(meta, dict):
            for k in self.title_keys:
                v = meta.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return f"conversation_{idx+1:03d}"

    def canonicalize(self, value: str, max_len: int = 120) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = value.replace("/", "-").replace("\\", "-")
        value = re.sub(r"[^\w\s\-\.\(\)&]+", "", value, flags=re.UNICODE)
        value = re.sub(r"\s+", " ", value).strip()
        value = value.replace(" ", "_")
        if not value:
            value = "untitled"
        if len(value) > max_len:
            value = value[:max_len].rstrip("._-")
        return value

    def create_unique_path(self, base: Path) -> Path:
        if not base.exists():
            return base
        i = 2
        stem, suffix = base.stem, base.suffix
        while True:
            candidate = base.with_name(f"{stem}__{i}{suffix}")
            if not candidate.exists():
                return candidate
            i += 1

    def copy_file_to_dir_if_new(self, out_dir, filename):
        destination_file = os.path.join(out_dir, os.path.basename(filename))
        if os.path.exists(destination_file):
            return destination_file
        try:
            shutil.copy2(filename, out_dir)
        except Exception as e:
            print(f"file exists: {destination_file}")
        return destination_file

    def create_file_locally_if_new(self, out_dir, filename, contents):
        filepath = f"{out_dir}/{filename}"
        try:
            with open(filepath, 'x') as f:
                f.write(contents)
        except Exception as e:
            foo = 1
        return filepath

    def md_to_html(self, text: str) -> str:
        # use markdown to simplify html presentation
        if not text:
            return ""
        return markdown.markdown(
            text,
            extensions=["fenced_code", "tables", "sane_lists", "codehilite"]
        )

    def process_code_content(self, content, msgs, author):
        text = content['text']
        text = f"code:{text}"
        msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})

    def process_thoughts_content(self, content, msgs, author):
        if 'thoughts' in content:
            self.process_multiple_thoughts_content(content, msgs, author)
        elif 'text' in content:
            text = content['text']
            text = f"code:{text}"
            msgs.append({"role": author.get("role") or author.get("name") or "unknown","content": text})
        else:
            raise Exception("Unrecognized thought content")

    def process_multiple_thoughts_content(self, content, msgs, author):
        thoughts = content['thoughts']
        for thought in thoughts:
            thought_summary = thought['summary']
            thought_content = thought['content']
            text = f"thought:{thought_summary}:{thought_content}"
            msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})

    def process_text_upload_content(self, content, msgs, author, out_dir):
        file_contents = content['text']
        file_name = content['title']
        self.create_file_locally_if_new(out_dir, file_name, file_contents)
        text = f"text_file:{file_name}"
        msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})

    def process_other_content_types(self, content, msgs, author, content_type):
        content_content = content['content']  # reasoning_recap,
        text = f"{content_type}:{content_content}"
        msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})

    def process_image_upload_content(self, part, msgs, author, out_dir):
        asset_pointer = part['asset_pointer']
        if asset_pointer.startswith("file-service"):
            filename = f"{asset_pointer[15:]}*"
        elif asset_pointer.startswith("sediment"):
            filename = f"{asset_pointer[11:]}*"
        else:
            raise Exception(f"Unexpected asset pointer: {asset_pointer}")

        specific_files = []
        if 'metadata' in part: # dalle generations or user upload
            metadata = part['metadata']
            if metadata and ('dalle' in metadata) and (metadata['dalle'] is not None):
                filepath = f"dalle-generations/{filename}"
                specific_files = glob.glob(filepath)
                if len(specific_files) == 0:
                    filepath = f"user-*/{filename}"
                    specific_files = glob.glob(filepath)
                    if len(specific_files) == 0:
                        foo = 1
        if len(specific_files) == 0:
            specific_files = glob.glob(filename)
        for specific_file in specific_files:
            self.copy_file_to_dir_if_new(out_dir, specific_file)
            text = f"image_file:{specific_file}"
            msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})
        if len(specific_files) == 0:
            print(f"could not find image file for {asset_pointer}")

    def process_conversation_content(self, content, msgs, author, out_dir):
        if "parts" in content:  # content_type: text
            parts = content["parts"]
            for part in parts:
                if not part: continue
                if isinstance(part, dict):
                    content_type = part['content_type']
                    if content_type == 'image_asset_pointer':
                        self.process_image_upload_content(part, msgs, author, out_dir)
                        continue
                    else:
                        foo = 1
                elif isinstance(part, str):
                    text = f"conversation:{part}\n"
                    msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})
                else:
                    raise Exception(f"Unexpected conversation format: {part}")

    def process_multimodal_text_content(self, content, msgs, author, out_dir):
        self.process_conversation_content(content, msgs, author, out_dir)

    def process_user_editable_content(self, content, msgs, author):
        if 'user_profile' in content:
            user_profile = content['user_profile']
            text = f"user_profile:{user_profile}"
            msgs.append({"role": author.get("role") or author.get("name") or "unknown", "content": text})
        else:
            raise Exception(f"Unexpected user content format: {content}")

    def process_content_type(self, content, msgs, author, content_type, out_dir):
        if content_type == 'text':  # conversation usually
            self.process_conversation_content(content, msgs, author, out_dir)
        elif content_type == "code":
            self.process_code_content(content, msgs, author)
        elif content_type == "thoughts":
            self.process_thoughts_content(content, msgs, author)
        elif content_type == 'text':
            self.process_conversation_content(content, msgs, author, out_dir)
        elif content_type == 'multimodal_text':
            self.process_multimodal_text_content(content, msgs, author, out_dir)
        elif content_type == 'user_editable_context':
            self.process_user_editable_content(content, msgs, author)
        elif content_type in ['execution_output', 'reasoning_recap', 'tether_browsing_display',
                              'tether_quote', 'system_error']:
            foo = 1 # do nothing
        else:
            self.process_other_content_types(content, msgs, author, content_type)

    def find_messages(self, conv: Dict[str, Any], out_dir: str) -> Optional[List[Dict[str, Any]]]:
        mapping = conv.get("mapping")
        if not isinstance(mapping, dict):
            raise Exception(f"Unrecognized mapping format: {mapping}")

        def key_fn(n: Dict[str, Any]):
            msg = n.get("message", {})
            if not msg: return 0.0
            t = msg.get("create_time") or n.get("create_time") or 0
            try:
                return float(t)
            except Exception:
                return 0.0

        nodes = [v for _, v in mapping.items() if isinstance(v, dict) and "message" in v]
        nodes.sort(key=key_fn)
        msgs = []
        for node in nodes:
            msg = node.get("message")
            if not msg: continue
            id = msg.get("id")
            if not isinstance(msg, dict):
                raise Exception(f"Unrecognized message format: {msg}")
            author = msg.get("author") or {}
            content = msg.get("content")
            if not isinstance(content, dict):
                raise Exception(f"Unrecognized content format: {content}")
            if "content_type" in content:
                content_type = content['content_type']
                self.process_content_type(content, msgs, author, content_type, out_dir)
            elif "text" in content:
                if not "title" in content:
                    foo = 1
                self.process_text_upload_content(content, msgs, author, out_dir)
                foo = 2
            elif 'thoughts' in content:
                self.process_thoughts_content(content, msgs, author)
            else: #
                raise Exception(f"Unrecognized content block: {content}")
        return msgs

    def get_role(self, m: Dict[str, Any]) -> str:
        role = m.get("role") or (m.get("author") or {}).get("role") or m.get("author") or m.get("sender")
        if isinstance(role, dict):
            role = role.get("role") or role.get("name")
        if not isinstance(role, str):
            role = "unknown"
        role = role.lower()
        label = self.role_map.get(role, role.capitalize())
        return label


    def message_to_html(self, message: dict, role_label) -> str:
        parts = ["<div class=\"message\">", f"<div class=\"role\">{html_escape(role_label)}</div>", '<div class="msg-body">']
        if 'content' in message:
            content = message['content']
            if not isinstance(content, str):
                raise Exception(f"Unrecognized content type: {content}")
            if content.startswith("image_file:"):
                image_path = content[11:]
                html = f'<img src="{image_path}">'
                parts.append(html)
            elif content.startswith("conversation:"):
                text = content[13:]
                html = self.md_to_html(text)
                parts.append(html)
            elif content.startswith("code:"):
                text = content[5:]
                html = self.md_to_html(text)
                parts.append(html)
            elif content.startswith("text_file:"):
                text = content[10:]
                html = f"<a href='{text}' target='_blank'>{text}</a>\n"
                parts.append(html)
            elif content.startswith("thought:"):
                text = content[8:]
                html = f"thought:{text}'>\n"
                parts.append(html)
            elif content.startswith("reasoning_recap:"):
                text = content[16:]
                html = f"reasoning_recap:{text}'>\n"
                parts.append(html)
            elif content.startswith("user_profile:"):
                text = content[13:]
                html = f"user_profile:{text}'>\n"
                parts.append(html)
            else:
                raise Exception(f"Unrecognized content type: {content}")
        parts.append("</div></div></div>")
        result = "\n".join(parts)
        return result

    def text_to_html(self, text: str) -> str:
        if not text:
            return ""
        return "<p>" + html_escape(text).replace("\n", "<br>") + "</p>"

    def build_index(self, items: List[tuple]) -> str:
        cards = []
        try:
            for title, fname in items:
                cards.append(f'<div class="card" data-title="{html_escape(title.lower())}">'
                             f'<h3><a href="{html_escape(fname)}">{html_escape(title)}</a></h3>'
                             f'<div class="small">{html_escape(fname)}</div>'
                             f'</div>')
        except Exception as ex:
            foo = 1
        try:
            index_html = self.get_index_html()
            base_css = self.get_base_css()
            html = index_html.format(site_title="Conversations", css=base_css, items="\n".join(cards))
            return html
        except Exception as ex:
            raise ex

if __name__ == '__main__':
    cmdln_args = " ".join(sys.argv)
    op = OptionParser()
    op.banner = "Export conversations to html."
    op.add_option("-f", "--file", dest="input_file", default=Path("conversations.json"),
                  help="Path to conversations.json export")
    op.add_option("-o", "--out-dir", dest="out_dir", default=Path("site_out"), help="Output directory")
    op.add_option("-u", "--user-name", dest="user_name", default="User", help="Label for user messages")
    op.add_option("-a", "--assistant-name", dest="assistant_name", default="Assistant",
                  help="Label for assistant messages")

    (options, args) = op.parse_args()

    input_file     = options.input_file
    out_dir        = options.out_dir
    user_name      = options.user_name
    assistant_name = options.assistant_name

    chat_to_html = ChatLogToHtml(user_name, assistant_name)
    input_file = Path(input_file)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    convs = chat_to_html.load_conversations(input_file, out_dir)
    chat_to_html.generate_html(convs, out_dir)




