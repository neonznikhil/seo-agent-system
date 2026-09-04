from weasyprint import HTML, CSS
from pathlib import Path

html_path = Path(r"C:\Users\nikhil\Desktop\seo-agent-system\rankforge_blueprint.html")
pdf_path = Path(r"C:\Users\nikhil\Desktop\seo-agent-system\rankforge_blueprint.pdf")

print(f"Converting {html_path} to PDF...")
HTML(filename=str(html_path)).write_pdf(str(pdf_path))
print(f"PDF created at: {pdf_path}")
print(f"PDF size: {pdf_path.stat().st_size / 1024 / 1024:.2f} MB")
