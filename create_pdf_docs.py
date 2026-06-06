#!/usr/bin/env python3
"""
Script to combine all PolyOne documentation into a single PDF file.
"""

import os
import sys
from pathlib import Path

try:
    import markdown
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    print("Required packages not found. Installing...")
    print("Please run: pip install markdown weasyprint")
    sys.exit(1)


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


def combine_documentation() -> str:
    """Combine all documentation files into a single markdown document."""
    
    # Define the order of documentation sections
    docs_order = [
        ("POLYONE_BOT_DOCUMENTATION.md", "Quick Start Guide"),
        ("ENV_VARIABLES.md", "Environment Variables Reference"),
        ("COMMANDS_REFERENCE.md", "Commands Reference"),
        ("USE_CASE_EXAMPLES.md", "Use Case Examples"),
        ("DEPLOYMENT.md", "Deployment Guide"),
        ("CHANGELOG.md", "Changelog"),
    ]
    
    combined = []
    
    # Add title page
    from datetime import datetime
    combined.append("# PolyOne Bot - Complete Documentation\n\n")
    combined.append("**Version:** 1.3.0\n\n")
    combined.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    combined.append("---\n\n")
    combined.append("# Table of Contents\n\n")
    
    # Build table of contents
    toc_items = []
    for filename, title in docs_order:
        anchor = title.lower().replace(" ", "-")
        toc_items.append(f"1. [{title}](#{anchor})")
    combined.append("\n".join(toc_items))
    combined.append("\n\n---\n\n")
    
    # Add each documentation section
    for filename, title in docs_order:
        if os.path.exists(filename):
            combined.append(f"# {title}\n\n")
            content = read_markdown_file(filename)
            if content:
                combined.append(content)
                combined.append("\n\n---\n\n")
        else:
            print(f"Warning: {filename} not found, skipping...")
    
    return "\n".join(combined)


def markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML."""
    md = markdown.Markdown(extensions=['extra', 'codehilite', 'tables', 'toc'])
    html_body = md.convert(markdown_content)
    
    # Create full HTML document with styling
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PolyOne Bot - Complete Documentation</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @top-center {{
                content: "PolyOne Bot Documentation";
            }}
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
            }}
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
        }}
        
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            page-break-after: avoid;
        }}
        
        h2 {{
            color: #34495e;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
            margin-top: 30px;
            page-break-after: avoid;
        }}
        
        h3 {{
            color: #555;
            margin-top: 20px;
            page-break-after: avoid;
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
            page-break-inside: avoid;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            page-break-inside: avoid;
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
        
        .page-break {{
            page-break-before: always;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
    
    return html


def create_pdf(html_content: str, output_file: str = "PolyOne_Complete_Documentation.pdf"):
    """Convert HTML to PDF using WeasyPrint."""
    try:
        print(f"Creating PDF: {output_file}...")
        HTML(string=html_content).write_pdf(output_file)
        print(f"✓ PDF created successfully: {output_file}")
        return True
    except Exception as e:
        print(f"Error creating PDF: {e}")
        return False


def main():
    """Main function to combine documentation and create PDF."""
    print("PolyOne Documentation PDF Generator")
    print("=" * 50)
    
    # Combine all documentation
    print("\n1. Combining documentation files...")
    combined_md = combine_documentation()
    
    if not combined_md:
        print("Error: No documentation content found!")
        return
    
    print(f"✓ Combined {len(combined_md)} characters of documentation")
    
    # Convert to HTML
    print("\n2. Converting markdown to HTML...")
    html_content = markdown_to_html(combined_md)
    print("✓ HTML conversion complete")
    
    # Create PDF
    print("\n3. Generating PDF...")
    if create_pdf(html_content):
        file_size = os.path.getsize("PolyOne_Complete_Documentation.pdf") / 1024
        print(f"\n✓ Success! PDF file size: {file_size:.2f} KB")
        print(f"\nOutput file: PolyOne_Complete_Documentation.pdf")
    else:
        print("\n✗ Failed to create PDF")
        sys.exit(1)


if __name__ == "__main__":
    main()

