from lark import Lark, Transformer, v_args
import sys
from querystring_parser import parser

# IIC grammar definition (final version: single-line attributes only)
iic_grammar = r"""
%import common.NEWLINE
%import common.WS_INLINE
%ignore WS_INLINE

start: (element | NEWLINE)*

element: meta_block | content_block

meta_block: META_START NEWLINE block_body META_END
content_block: BLOCK_START NEWLINE block_body BLOCK_END

block_body: attribute_list NEWLINE* text_content?
text_content: TEXT_LINE+

attribute_list: attribute*
attribute: name COLON value NEWLINE
value: /[^\n]+/

TEXT_LINE: /(?!(<\/?ii-(meta|block)>))([^\n]+)/ NEWLINE?
name: /[a-zA-Z_][a-zA-Z0-9_-]*/

COLON: ":"
META_START: "<ii-meta>"
META_END: "</ii-meta>"
BLOCK_START: "<ii-block>"
BLOCK_END: "</ii-block>"
"""

IICBlockTypeMeta = "meta"
IICBlockTypeBlock = "block"

@v_args(inline=True)
class IICTransformer(Transformer):
    def start(self, *elements):
        return [e for e in elements if e is not None and (not isinstance(e, str) or e.strip())]

    def meta_block(self, _start, _newline, body, _end):
        return {"type": IICBlockTypeMeta, **body}

    def content_block(self, _start, _newline, body, _end):
        return {"type": IICBlockTypeBlock, **body}

    def block_body(self, attr_list, text_content=None):
        result = {"attributes": attr_list}
        if text_content:
            lines = text_content.strip().split('\n')
            content_lines = []
            in_content = False
            
            for line in lines:
                # An empty line marks the end of the attribute section, and the rest is content
                if not line.strip():
                    in_content = True
                    continue
                
                if not in_content:
                    # In the attribute section, try to parse as a key-value pair
                    if ': ' in line:
                        key, value = line.split(': ', 1)
                        if key.strip().isidentifier():
                            result["attributes"][key.strip()] = value.strip()
                            continue
                    # If this line cannot be parsed as a key-value pair, it means the attribute section has ended
                    in_content = True
                
                if in_content:
                    content_lines.append(line)
            
            # Store the content (if any)
            if content_lines:
                result["content"] = '\n'.join(content_lines)
        
        return result

    def text_content(self, *lines):
        return "\n".join(str(line).strip() for line in lines)

    def attribute_list(self, *attrs):
        result = {}
        for key, value in attrs:
            if key == "params":
                # Use querystring-parser to handle nested keys
                result[key] = parser.parse(value)
            else:
                result[key] = value.strip()
        return result

    def attribute(self, name, _colon, value, _newline):
        return (str(name), str(value).strip())

    def name(self, name):
        return str(name)

    def value(self, value):
        return str(value)

class IICBlock:
    def __init__(self, type, attributes, content):
        self.type = type
        self.attributes = attributes
        self.content = content

    def __repr__(self):
        return f"<IICBlock type={self.type} attributes={self.attributes} content={self.content[:20] if self.content else ''}>"

    def to_dict(self):
        return {
            "type": self.type,
            "attributes": self.attributes,
            "content": self.content
        }

    def to_iic(self):
        """Serialize to IIC grammar text, with attributes sorted by key."""
        if self.type == IICBlockTypeMeta:
            start, end = "<ii-meta>", "</ii-meta>"
        elif self.type == IICBlockTypeBlock:
            start, end = "<ii-block>", "</ii-block>"
        else:
            return ""
        lines = [start]
        for k in sorted(self.attributes.keys()):
            v = self.attributes[k]
            # params supports dictionary expansion
            if k == "params" and isinstance(v, dict):
                from urllib.parse import urlencode, unquote_plus
                def _flatten(d, prefix=""):
                    items = []
                    for key, value in d.items():
                        if isinstance(value, dict):
                            items.extend(_flatten(value, f"{prefix}{key}["))
                        elif isinstance(value, list):
                            for item in value:
                                items.append((f"{prefix}{key}[]", item))
                        else:
                            items.append((f"{prefix}{key}", value))
                    return items
                flat = _flatten(v)
                v = unquote_plus(urlencode(flat, doseq=True))
            if self.type == IICBlockTypeMeta and k == "id":
                continue
            lines.append(f"{k}: {v}")
        if self.content and self.content.strip():
            lines.append("")
            lines.extend(self.content.strip().splitlines())
        lines.append(end)
        return "\n".join(lines)

def parse_iic(source, to_dict=False):
    parser = Lark(iic_grammar, parser="lalr", maybe_placeholders=False)
    tree = parser.parse(source)
    transformer = IICTransformer()
    result = transformer.transform(tree)

    def extract_element(obj: dict):
        type = obj.get("type")
        attributes = obj.get("attributes")
        content = obj.get("content")

        return IICBlock(type, attributes, content)

    def extract(obj):
        from lark.tree import Tree
        if isinstance(obj, Tree):
            return extract(obj.children)
        if isinstance(obj, list):
            return [extract(x) for x in obj]
        return extract_element(obj)

    def flatten(obj):
        if isinstance(obj, list):
            return [item for sublist in obj for item in flatten(sublist)]
        return [obj]

    extracted_result = extract(result)
    flattened_result = flatten(extracted_result)
    if to_dict:
        return [block.to_dict() for block in flattened_result if isinstance(block, IICBlock)]
    return flattened_result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parser.py <file.iic>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        content = f.read()

    result = parse_iic(content, True)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
