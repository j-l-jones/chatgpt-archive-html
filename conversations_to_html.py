#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export conversations JSON to readable HTML pages (one per conversation) plus an index.html.
- Renders only conversation content (user/assistant by default; can include system/tool).
- Embeds images and referenced files.

Usage:
  python conversations_to_html.py -f conversations.json --user-name "Foo" --assistant-name "Chat Friend"  --out-dir site_out
"""

import datetime
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
from typing import Any, Dict, List, Optional
import unicodedata



class ChatLogToHtml:

    def __init__(self, user_name: str, assistant_name: str, archive_dir: Path):
        self.root_list_keys = ("conversations", "items", "data", "threads") # ??
        self.message_keys = ("messages", "msgs", "entries") # ??
        self.archive_dir = archive_dir

        self.role_map = {
            "user": user_name,
            "assistant": assistant_name,
            "system": "System",
            "tool": "Tool",
            "developer": "Developer",
            "function": "Function",
            "unknown": "Message",
        }

    # html related accessors
    def get_base_css(self):
        base_css = """
        :root { --bg:#0b0c10; --fg:#f0f3f6; --muted:#a3b3c2; --accent:#9ae6b4; --chip:#20232a; --card:#111318; }
        * { box-sizing: border-box; }
        html, body { margin:0; padding:0; background:var(--bg); color:var(--fg); font: 16px/1.55 system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji; }
        a { color: #8ab4ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .container { max-width: 980px; margin: 0 auto; padding: 28px 16px 80px; }
        .title-block { display:flex; flex-direction:column; }
        .meta-date { color: var(--muted); font-weight:600; margin-top:2px; }
        .header h1 { font-size: 24px; margin:0; }
        .title { font-size: 28px; margin: 12px 0 20px; }
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
        .meta-date { color: var(--muted); font-weight:600; margin-top:2px; }
        .code-wrap { position: relative; }
        .msg-body pre.collapsible { max-height: 18rem; overflow: auto; transition: max-height .2s ease; }
        .message { border-left:4px solid transparent; padding-left:12px; }
        
        .badge { ... border:1px solid #2a2f3a; background:#111318; color:#a3b3c2; }
         /* color accents per recipient */
        .message.message--r-bio { border-left-color:#10b981; background:rgba(16,185,129,.06); }
        .message.message--r-web,
        .message.message--r-web-run,
        .message.message--r-web-search { border-left-color:#60a5fa; background:rgba(96,165,250,.06); }
        .message.message--r-python { border-left-color:#f59e0b; background:rgba(245,158,11,.06); }
        .message.message--r-browser { border-left-color:#a78bfa; }
        .message.message--r-canmore-create_textdoc,
        .message.message--r-canmore-update_textdoc { border-left-color:#22d3ee; }
        .message[class*="message--r-t2uay3k"] { border-left-color:#ef4444; }

        /* Shaded fade at bottom when collapsed */
        .code-wrap.shaded::after {
          content: "";
          position: absolute;
          left: 0; right: 0;
          bottom: 2.6rem;           /* leave space for the button */
          height: 3.2rem;
          pointer-events: none;
          background: linear-gradient(to bottom, rgba(11,12,16,0), rgba(11,12,16,0.95));
          border-bottom-left-radius: 10px;
          border-bottom-right-radius: 10px;
        }
        
        /* Toggle button */
        .toggle {
          margin-top: .5rem;
          appearance: none;
          border: 1px solid #2a2f3a;
          background: #111318;
          color: #a3b3c2;
          padding: 6px 10px;
          border-radius: 8px;
          font-size: .9em;
          cursor: pointer;
        }
        .toggle:hover { background:#151923; }
        
        /* Optional: also collapse very long plain-text messages */
        .msg-body.collapsible { max-height: 22rem; overflow: hidden; position: relative; }
        .msg-body.collapsible.shaded::after {
          content:""; position:absolute; left:0; right:0; bottom:2.6rem; height:3.2rem;
          pointer-events:none; background: linear-gradient(to bottom, rgba(11,12,16,0), rgba(11,12,16,0.95));
        }
        """
        return base_css

    def get_index_html(self):
        index_html = """
        <!doctype html>
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
        page_html = """
        <!doctype html>
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
            <h6>{date}</h6>
          </div>
          {body}
        </div>
        <script>
        (function () {{
          const CODE_LINE_THRESHOLD = 20;
          const CODE_CHAR_THRESHOLD = 1200;
          const MSG_HEIGHT_THRESHOLD = 800;

          function makeCollapsible(target, linesLabel) {{
            const wrap = document.createElement('div');
            wrap.className = 'code-wrap shaded';
            target.parentNode.insertBefore(wrap, target);
            wrap.appendChild(target);

            target.classList.add('collapsible');

            const btn = document.createElement('button');
            btn.className = 'toggle';
            btn.setAttribute('aria-expanded', 'false');
            btn.textContent = linesLabel ? `Show all (${{linesLabel}})` : 'Show all';
            btn.addEventListener('click', () => {{
              const open = target.classList.toggle('open');
              if (open) {{
                target.style.maxHeight = 'none';
                btn.textContent = 'Hide';
                btn.setAttribute('aria-expanded', 'true');
                wrap.classList.remove('shaded');
              }} else {{
                target.style.maxHeight = '';
                btn.textContent = linesLabel ? `Show all (${{linesLabel}})` : 'Show all';
                btn.setAttribute('aria-expanded', 'false');
                wrap.classList.add('shaded');
                target.scrollIntoView({{ block: 'nearest' }});
              }}
            }});
            wrap.appendChild(btn);
          }}

          // Collapse long code blocks
          document.querySelectorAll('.msg-body pre').forEach(pre => {{
            const text = pre.textContent || '';
            const lines = text.split('\\n').length;
            if (lines > CODE_LINE_THRESHOLD || text.length > CODE_CHAR_THRESHOLD) {{
              makeCollapsible(pre, `${{lines}} lines`);
            }}
          }});
          // (Optional) Collapse long non-code messages
          document.querySelectorAll('.msg-body').forEach(body => {{
            if (body.querySelector('pre')) return; // skip if already handled as code
            const h = body.scrollHeight;
            if (h > MSG_HEIGHT_THRESHOLD) {{
              body.classList.add('collapsible','shaded');
              const btn = document.createElement('button');
              btn.className = 'toggle';
              btn.textContent = 'Show all';
              btn.setAttribute('aria-expanded','false');
              btn.addEventListener('click', () => {{
                const open = body.classList.toggle('open');
                if (open) {{
                  body.style.maxHeight = 'none';
                  btn.textContent = 'Hide';
                  btn.setAttribute('aria-expanded','true');
                  body.classList.remove('shaded');
                }} else {{
                  body.style.maxHeight = '';
                  btn.textContent = 'Show all';
                  btn.setAttribute('aria-expanded','false');
                  body.classList.add('shaded');
                  body.scrollIntoView({{ block: 'nearest' }});
                }}
              }});
              // Insert button after the body’s last child
              const parent = body.parentElement;
              parent.appendChild(btn);
            }}
          }});
        }})();
        </script>
        </body>
        </html>
        """
        return page_html

    # accessors
    def get_date(self, d):
        ts = d.get("create_time") or d.get("update_time")
        if not ts:
          return ""
        dt = datetime.datetime.fromtimestamp(ts)
        fmt = "%B %-d, %Y %-I:%M %p"
        if sys.platform.startswith("win"):
          fmt = "%B %#d, %Y %#I:%M %p"
        return dt.strftime(fmt)

    def get_unique_path(self, title, out_dir: Path) -> Path:
        fname = self.canonicalize(title) + ".html"
        out_path = (out_dir / fname)
        if not out_path.exists():
            return out_path
        i = 2
        stem, suffix = out_path.stem, out_path.suffix
        while True:
            candidate = out_path.with_name(f"{stem}__{i}{suffix}")
            if not candidate.exists():
                return candidate
            i += 1

    def get_recipient(self, msg):
        if 'recipient' in msg:
            recipient = msg['recipient']
            return recipient
        return None

    def get_role(self, m: Dict[str, Any]) -> str:
        role = m.get("role") or (m.get("author") or {}).get("role") or m.get("author") or m.get("sender")
        if isinstance(role, dict):
            role = role.get("role") or role.get("name")
        if not isinstance(role, str):
            role = "unknown"
        role = role.lower()
        label = self.role_map.get(role, role.capitalize())
        return label

    def get_author(self, author: Dict[str, Any]) -> str:
        return author.get("role") or author.get("name") or "unknown"

    # text processing
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

    # file related
    def copy_file_to_dir_if_new(self, out_dir, filename):
        destination_file = os.path.join(out_dir, os.path.basename(filename))
        if os.path.exists(destination_file):
            return destination_file
        try:
            shutil.copy2(filename, out_dir)
        except Exception as e:
            print(f"file exists: {destination_file}")
        return destination_file

    def create_file_if_new(self, out_dir, filename, contents):
        filepath = f"{out_dir}/{filename}"
        try:
            with open(filepath, 'x') as f:
                f.write(contents)
        except Exception as ex:
            raise ex
        return filepath

    def find_image(self, metadata, filename):
        if metadata and ('dalle' in metadata) and (metadata['dalle'] is not None):
            filepath = os.path.join(self.archive_dir, "dalle-generations", filename)
            files = glob.glob(filepath)
            if len(files) > 0:
                return files
            filepath = os.path.join(self.archive_dir, "user-*", filename)
            files = glob.glob(filepath)
            if len(files) > 0:
                return files
        return []

    # html formatting
    def md_to_html(self, text: str) -> str:
        # use markdown to simplify html presentation
        if not text:
            return ""
        return markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists", "codehilite"])

    # parsing
    def process_messages(self, conv: Dict[str, Any], out_dir: str) -> Optional[List[Dict[str, Any]]]:
        mapping = conv.get("mapping")
        if not isinstance(mapping, dict):
            raise Exception(f"Unrecognized mapping format")

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
            if not isinstance(msg, dict):
                raise Exception(f"Unrecognized message format: {msg}")
            id = msg.get("id")
            author = self.get_author(msg.get("author") or {})
            content = msg.get("content")
            recipient = self.get_recipient(msg)
            if not isinstance(content, dict):
                raise Exception(f"Unrecognized content format: {content}")
            if "content_type" in content:
                content_type = content['content_type']
                self.process_content_type(content, msgs, author, recipient, content_type, out_dir)
            elif "text" in content:
                self.process_text_upload_content(content, msgs, author, recipient, out_dir)
                foo = 2
            elif 'thoughts' in content:
                self.process_thoughts_content(content, msgs, author, recipient)
            else: #
                raise Exception(f"Unrecognized content block: {content}")
        return msgs

    def process_code_content(self, content, msgs, author, recipient):
        text = f"code:{content['text']}"
        msgs.append({"role": author, "audience": recipient, "content": text})

    def process_thoughts_content(self, content, msgs, author, recipient):
        if 'thoughts' in content:
            self.process_multiple_thoughts_content(content, msgs, author, recipient)
        elif 'text' in content:
            text = content['text']
            text = f"code:{text}"
            msgs.append({"role": author, "audience": recipient, "content": text})
        else:
            raise Exception("Unrecognized thought content")

    def process_multiple_thoughts_content(self, content, msgs, author, recipient):
        thoughts = content['thoughts']
        for thought in thoughts:
            thought_summary = thought['summary']
            thought_content = thought['content']
            text = f"thought:{thought_summary}:{thought_content}"
            msgs.append({"role": author, "audience": recipient, "content": text})

    def process_text_upload_content(self, content, msgs, author, recipient, out_dir):
        file_contents = content['text']
        file_name = content['title']
        self.create_file_if_new(out_dir, file_name, file_contents)
        text = f"text_file:{file_name}"
        msgs.append({"role": author, "audience": recipient, "content": text})

    def process_other_content_types(self, content, msgs, author, recipient, content_type):
        content_content = content['content']  # reasoning_recap,
        text = f"{content_type}:{content_content}"
        msgs.append({"role": author, "audience": recipient, "content": text})

    def process_image_content(self, part, msgs, author, recipient, out_dir):
        asset_pointer = part['asset_pointer']
        if asset_pointer.startswith("file-service"):
            filename = f"{asset_pointer[15:]}*"
        elif asset_pointer.startswith("sediment"):
            filename = f"{asset_pointer[11:]}*"
        else:
            raise Exception(f"Unexpected asset pointer: {asset_pointer}")

        files = []
        if 'metadata' in part: # dalle generations or user upload
            metadata = part['metadata']
            files = self.find_image(metadata, filename)
        if len(files) == 0:
            path = os.path.join(self.archive_dir, filename)
            files = glob.glob(path)
        for specific_file in files:
            copied = self.copy_file_to_dir_if_new(out_dir, specific_file)
            rel = os.path.basename(copied)
            msgs.append({"role": author, "audience": recipient, "content": f"image_file:{rel}"})
        if len(files) == 0:
            print(f"could not find image file for {asset_pointer}")

    def process_conversation_content(self, content, msgs, author, recipient, out_dir):
        if "parts" not in content:
            raise Exception(f"Unexpected conversation format")
        parts = content["parts"] # list
        for part in parts:
            if not part: continue
            if isinstance(part, dict): # dict or str
                content_type = part['content_type']
                if content_type == 'image_asset_pointer':
                    self.process_image_content(part, msgs, author, recipient, out_dir)
                    continue
                else:
                    raise Exception(f"Some other content type? {content_type}")
            elif isinstance(part, str):
                text = f"conversation:{part}\n"
                msgs.append({"role": author, "audience": recipient, "content": text})
            else:
                raise Exception(f"Unexpected conversation part: {part}")

    def process_multimodal_text_content(self, content, msgs, author, recipient, out_dir):
        self.process_conversation_content(content, msgs, author, recipient, out_dir)

    def process_user_editable_content(self, content, msgs, author, recipient):
        if 'user_profile' in content:
            user_profile = content['user_profile']
            text = f"user_profile:{user_profile}"
            msgs.append({"role": author, "audience": recipient, "content": text})
        else:
            raise Exception(f"Unexpected user content format: {content}")

    def process_content_type(self, content, msgs, author, recipient, content_type, out_dir):
        if content_type == 'text':  # conversation usually
            self.process_conversation_content(content, msgs, author, recipient, out_dir)
        elif content_type == "code":
            self.process_code_content(content, msgs, author, recipient)
        elif content_type == "thoughts":
            self.process_thoughts_content(content, msgs, author, recipient)
        elif content_type == 'text':
            self.process_conversation_content(content, msgs, author, recipient, out_dir)
        elif content_type == 'multimodal_text':
            self.process_multimodal_text_content(content, msgs, author, recipient, out_dir)
        elif content_type == 'user_editable_context':
            self.process_user_editable_content(content, msgs, author, recipient)
        elif content_type in ['execution_output', 'reasoning_recap', 'tether_browsing_display',
                              'tether_quote', 'system_error']:
            foo = 1 # do nothing
        else:
            self.process_other_content_types(content, msgs, author, recipient, content_type)

    # json
    def load_conversations(self, in_file: Path, out_dir: Path) -> List[Dict[str, Any]]:
        with in_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise Exception(f"Unexpected format for {in_file}")
        return data

    # generate
    def build_index(self, items: List[tuple]) -> str:
        cards = []
        try:
            for title, fname, created in items:
                cards.append(f'<div class="card" data-title="{html_escape(title.lower())}">'
                             f'<h3><a href="{html_escape(fname)}">{html_escape(title)}</a></h3>'
                             f'<div class="small">{html_escape(created)}</div>'
                             f'</div>')
        except Exception as ex:
            raise ex
        try:
            index_html = self.get_index_html()
            base_css = self.get_base_css()
            html = index_html.format(site_title="Conversations", css=base_css, items="\n".join(cards))
            return html
        except Exception as ex:
            raise ex

    # html
    def message_to_html(self, message: dict, role_label) -> str:
        recipient = (message.get("audience") or "").strip().lower().replace(".", "-")
        rec_cls = f" message--r-{recipient}" if recipient else ""
        rec_badge = f'<span class="badge">{html_escape(recipient)}</span>' if recipient else ""
        parts = [f'<div class="message{rec_cls}">',
                 f'<div class="role">{html_escape(role_label)}{rec_badge}</div>',
                 '<div class="msg-body">']
        if 'content' in message:
            content = message['content']
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
                html = f"thought:{text}>\n"
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
        parts.append("</div></div>")
        result = "\n".join(parts)
        return result

    def generate_html(self, convs, out_dir):
        index_items = []
        for i, conv in enumerate(convs):
            if i > 10: break
            title = conv['title']
            if not title: title = "Untitled"
            out_path = self.get_unique_path(title, out_dir)
            created = self.get_date(conv)
            msgs = self.process_messages(conv, out_dir) or []
            messages = []
            for m in msgs:
                label = self.get_role(m)
                html = self.message_to_html(m, label)
                messages.append(html)

            page_html = self.get_page_html()
            base_css = self.get_base_css()
            title = html_escape(title)
            body = "\n".join(messages)
            html = page_html.format(title=title, date=created, css=base_css, body=body)
            out_path.write_text(html, encoding="utf-8")
            index_items.append((title, out_path.name, created))

        index_html = self.build_index(index_items)
        (out_dir / "index.html").write_text(index_html, encoding="utf-8")

        print(f"Wrote {len(index_items)} pages to {out_dir.resolve()} (open index.html)")

    def generate(self, input_file, out_dir):
        convs = chat_to_html.load_conversations(input_file, out_dir)
        chat_to_html.generate_html(convs, out_dir)


if __name__ == '__main__':
    cmdln_args = " ".join(sys.argv)
    op = OptionParser()
    op.banner = "Export conversations to html."
    op.add_option("-d", "--archive-dir", dest="archive_dir", default=Path("archive"), help="Input directory")
    op.add_option("-f", "--file", dest="input_file", default=Path("conversations.json"),
                  help="Path to conversations.json export")
    op.add_option("-o", "--out-dir", dest="out_dir", default=Path("site_out"), help="Output directory")
    op.add_option("-u", "--user-name", dest="user_name", default="User", help="Label for user messages")
    op.add_option("-a", "--assistant-name", dest="assistant_name", default="Assistant",
                  help="Label for assistant messages")

    (options, args) = op.parse_args()

    input_file     = options.input_file
    archive_dir    = options.archive_dir
    out_dir        = options.out_dir
    user_name      = options.user_name
    assistant_name = options.assistant_name

    chat_to_html = ChatLogToHtml(user_name, assistant_name, archive_dir)
    input_file = Path(input_file)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chat_to_html.generate(input_file, out_dir)

