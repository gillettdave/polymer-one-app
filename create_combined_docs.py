#!/usr/bin/env python3
"""
Script to combine all PolyOne documentation into a single markdown and HTML file.
The HTML file can be printed to PDF from any browser.
"""

import os
from datetime import datetime


def read_markdown_file(filepath: str) -> str:
    """Read a markdown file and return its content."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
        return ""
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""


def combine_documentation() -> tuple[str, str]:
    """Combine all documentation files into markdown and HTML."""
    
    # Define the order of documentation sections
    docs_order = [
        ("POLYONE_BOT_DOCUMENTATION.md", "Quick Start Guide"),
        ("ENV_VARIABLES.md", "Environment Variables Reference"),
        ("COMMANDS_REFERENCE.md", "Commands Reference"),
        ("USE_CASE_EXAMPLES.md", "Use Case Examples"),
        ("DEPLOYMENT.md", "Deployment Guide"),
        ("CHANGELOG.md", "Changelog"),
    ]
    
    combined_md = []
    toc_items = []
    
    # Add title page
    combined_md.append("# PolyOne Bot - Complete Documentation\n\n")
    combined_md.append(f"**Version:** 1.3.0  \n")
    combined_md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    combined_md.append("---\n\n")
    combined_md.append("# Table of Contents\n\n")
    
    # Build table of contents
    for i, (filename, title) in enumerate(docs_order, 1):
        anchor = title.lower().replace(" ", "-").replace("'", "")
        toc_items.append(f"{i}. [{title}](#{anchor})")
    combined_md.append("\n".join(toc_items))
    combined_md.append("\n\n---\n\n")
    
    # Add each documentation section
    for filename, title in docs_order:
        if os.path.exists(filename):
            anchor = title.lower().replace(" ", "-").replace("'", "")
            combined_md.append(f"<a name='{anchor}'></a>\n\n")
            combined_md.append(f"# {title}\n\n")
            content = read_markdown_file(filename)
            if content:
                combined_md.append(content)
                combined_md.append("\n\n---\n\n")
        else:
            print(f"Warning: {filename} not found, skipping...")
    
    markdown_content = "\n".join(combined_md)
    
    # Convert markdown to HTML
    html_content = markdown_to_html(markdown_content)
    
    return markdown_content, html_content


def markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML with basic formatting."""
    
    # Simple markdown to HTML conversion
    html = markdown_content
    
    # Headers
    html = html.replace("\n# ", "\n<h1>").replace("\n## ", "\n<h2>").replace("\n### ", "\n<h3>")
    html = html.replace("\n#### ", "\n<h4>").replace("\n##### ", "\n<h5>")
    
    # Close headers (simple approach - find next newline or end)
    import re
    html = re.sub(r'<h1>(.+?)\n', r'<h1>\1</h1>\n', html)
    html = re.sub(r'<h2>(.+?)\n', r'<h2>\1</h2>\n', html)
    html = re.sub(r'<h3>(.+?)\n', r'<h3>\1</h3>\n', html)
    html = re.sub(r'<h4>(.+?)\n', r'<h4>\1</h4>\n', html)
    html = re.sub(r'<h5>(.+?)\n', r'<h5>\1</h5>\n', html)
    
    # Code blocks
    html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
    
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Italic
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Lists
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'^(\d+)\. (.+)$', r'<li>\2</li>', html, flags=re.MULTILINE)
    
    # Line breaks
    html = html.replace('\n\n', '</p><p>')
    html = html.replace('\n', '<br>\n')
    
    # Wrap in HTML structure
    html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PolyOne Bot - Complete Documentation</title>
    <style>
        @media print {{
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-size: 11pt;
            }}
            h1 {{
                page-break-after: avoid;
            }}
            h2, h3 {{
                page-break-after: avoid;
            }}
            pre {{
                page-break-inside: avoid;
            }}
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: white;
        }}
        
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        
        h2 {{
            color: #34495e;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
            margin-top: 30px;
        }}
        
        h3 {{
            color: #555;
            margin-top: 20px;
        }}
        
        h4 {{
            color: #666;
            margin-top: 15px;
        }}
        
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        pre {{
            background-color: #f4f4f4;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        ul, ol {{
            margin: 10px 0;
            padding-left: 30px;
        }}
        
        li {{
            margin: 5px 0;
        }}
        
        blockquote {{
            border-left: 4px solid #3498db;
            margin: 15px 0;
            padding-left: 15px;
            color: #666;
            font-style: italic;
        }}
        
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }}
        
        p {{
            margin: 10px 0;
        }}
    </style>
</head>
<body>
<p>{html}</p>
</body>
</html>"""
    
    return html_doc


def main():
    """Main function to combine documentation."""
    print("PolyOne Documentation Combiner")
    print("=" * 50)
    
    # Combine all documentation
    print("\n1. Combining documentation files...")
    markdown_content, html_content = combine_documentation()
    
    if not markdown_content:
        print("Error: No documentation content found!")
        return
    
    # Save combined markdown
    print("\n2. Saving combined markdown file...")
    with open("PolyOne_Complete_Documentation.md", "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print("[OK] Saved: PolyOne_Complete_Documentation.md")
    
    # Save HTML file
    print("\n3. Saving HTML file (can be printed to PDF from browser)...")
    with open("PolyOne_Complete_Documentation.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("[OK] Saved: PolyOne_Complete_Documentation.html")
    
    print("\n" + "=" * 50)
    print("[OK] Documentation files created successfully!")
    print("\nTo create a PDF:")
    print("1. Open 'PolyOne_Complete_Documentation.html' in your browser")
    print("2. Press Ctrl+P (or Cmd+P on Mac)")
    print("3. Select 'Save as PDF' as the destination")
    print("4. Click 'Save'")
    print("\nAlternatively, use an online markdown-to-PDF converter with")
    print("'PolyOne_Complete_Documentation.md'")


if __name__ == "__main__":
    main()

