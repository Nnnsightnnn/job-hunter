"""
PDF Compiler Module
Takes tailored resume JSON and compiles to PDF using LaTeX
"""
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

# Jinja2 for templating - install with: pip install jinja2
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    print("⚠️  Jinja2 not installed. Run: pip install jinja2")


class PDFCompiler:
    """
    Compiles tailored resume JSON to PDF using LaTeX templates
    """
    
    def __init__(
        self,
        templates_dir: str = "templates",
        output_dir: str = "output",
        temp_dir: str = ".latex_temp"
    ):
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 with LaTeX-friendly delimiters
        if JINJA_AVAILABLE:
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=False,  # LaTeX handles its own escaping
                block_start_string='<%',
                block_end_string='%>',
                variable_start_string='<<',
                variable_end_string='>>',
                comment_start_string='<#',
                comment_end_string='#>'
            )
    
    def _check_latex(self) -> bool:
        """Check if pdflatex is available"""
        try:
            result = subprocess.run(
                ["pdflatex", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters"""
        if not text:
            return ""
        
        # Characters that need escaping in LaTeX
        special_chars = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
        }
        
        for char, escaped in special_chars.items():
            text = text.replace(char, escaped)
        
        return text
    
    def _format_date(self, date_str: str) -> str:
        """Format date string for resume (YYYY-MM -> Month Year)"""
        if not date_str or date_str.lower() == "present":
            return "Present"
        
        try:
            if len(date_str) == 7:  # YYYY-MM format
                dt = datetime.strptime(date_str, "%Y-%m")
                return dt.strftime("%b %Y")
            elif len(date_str) == 10:  # YYYY-MM-DD format
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.strftime("%b %Y")
        except ValueError:
            pass
        
        return date_str
    
    def _prepare_template_data(self, resume_data: dict) -> dict:
        """Prepare resume data for LaTeX template injection"""
        personal = resume_data.get("personal", {})
        
        # Prepare experience with escaped text and formatted dates
        experience = []
        for job in resume_data.get("experience", []):
            exp = {
                "company": self._escape_latex(job.get("company", "")),
                "title": self._escape_latex(job.get("title", "")),
                "location": self._escape_latex(job.get("location", "")),
                "start_date": self._format_date(job.get("start_date", "")),
                "end_date": self._format_date(job.get("end_date", "Present")),
                "bullets": [self._escape_latex(b) for b in job.get("bullets", [])]
            }
            experience.append(exp)
        
        # Prepare education
        education = []
        for edu in resume_data.get("education", []):
            education.append({
                "institution": self._escape_latex(edu.get("institution", "")),
                "degree": self._escape_latex(edu.get("degree", "")),
                "field": self._escape_latex(edu.get("field", "")),
                "graduation_date": self._format_date(edu.get("graduation_date", "")),
                "gpa": edu.get("gpa", "")
            })
        
        # Prepare skills
        skills = resume_data.get("skills", {})
        skills_prepared = {
            "technical": [self._escape_latex(s) for s in skills.get("technical", [])],
            "tools": [self._escape_latex(s) for s in skills.get("tools", [])],
            "soft": [self._escape_latex(s) for s in skills.get("soft", [])],
            "certifications": [self._escape_latex(s) for s in skills.get("certifications", [])]
        }
        
        return {
            "name": self._escape_latex(personal.get("name", "")),
            "email": self._escape_latex(personal.get("email", "")),
            "phone": self._escape_latex(personal.get("phone", "")),
            "location": self._escape_latex(personal.get("location", "")),
            "linkedin": personal.get("linkedin", ""),
            "summary": self._escape_latex(resume_data.get("summary", personal.get("summary", ""))),
            "experience": experience,
            "education": education,
            "skills": skills_prepared
        }
    
    def compile_pdf(
        self,
        resume_json_path: str,
        template_name: str = "resume_template.tex",
        output_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Compile a tailored resume JSON to PDF
        
        Args:
            resume_json_path: Path to the tailored resume JSON
            template_name: Name of the LaTeX template file
            output_name: Custom output filename (without extension)
        
        Returns:
            Path to the generated PDF or None if failed
        """
        if not JINJA_AVAILABLE:
            raise ImportError("Jinja2 is required. Run: pip install jinja2")
        
        if not self._check_latex():
            raise EnvironmentError("pdflatex not found. Install TeX Live or MiKTeX.")
        
        # Load resume data
        resume_path = Path(resume_json_path)
        if not resume_path.exists():
            raise FileNotFoundError(f"Resume JSON not found: {resume_path}")
        
        with open(resume_path, 'r') as f:
            resume_data = json.load(f)
        
        # Prepare data for template
        template_data = self._prepare_template_data(resume_data)
        
        # Load and render template
        template = self.env.get_template(template_name)
        rendered_latex = template.render(**template_data)
        
        # Write to temp file
        job_id = resume_data.get("job_id", "resume")
        company = resume_data.get("company", "").lower().replace(" ", "_")[:15]
        
        if output_name:
            base_name = output_name
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            base_name = f"resume_{company}_{job_id}_{timestamp}"
        
        tex_file = self.temp_dir / f"{base_name}.tex"
        with open(tex_file, 'w') as f:
            f.write(rendered_latex)
        
        print(f"📄 Compiling PDF: {base_name}.pdf")
        
        # Compile with pdflatex (run twice for proper formatting)
        try:
            for i in range(2):
                result = subprocess.run(
                    [
                        "pdflatex",
                        "-interaction=nonstopmode",
                        "-output-directory", str(self.temp_dir),
                        str(tex_file)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0 and i == 1:
                    print(f"⚠️  LaTeX warnings (usually safe to ignore)")
            
            # Move PDF to output directory
            pdf_temp = self.temp_dir / f"{base_name}.pdf"
            pdf_output = self.output_dir / f"{base_name}.pdf"
            
            if pdf_temp.exists():
                shutil.move(str(pdf_temp), str(pdf_output))
                print(f"✅ PDF created: {pdf_output}")
                return pdf_output
            else:
                print(f"❌ PDF compilation failed")
                print(f"   Check logs in: {self.temp_dir}")
                return None
                
        except subprocess.TimeoutExpired:
            print("❌ LaTeX compilation timed out")
            return None
        except Exception as e:
            print(f"❌ Compilation error: {e}")
            return None
    
    def compile_from_dict(
        self,
        resume_data: dict,
        template_name: str = "resume_template.tex",
        output_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Compile directly from a resume dictionary (without saving JSON first)
        """
        # Save to temp JSON
        temp_json = self.temp_dir / "temp_resume.json"
        with open(temp_json, 'w') as f:
            json.dump(resume_data, f)
        
        return self.compile_pdf(str(temp_json), template_name, output_name)
    
    def cleanup_temp(self):
        """Remove temporary LaTeX files"""
        if self.temp_dir.exists():
            for ext in [".aux", ".log", ".out", ".tex"]:
                for f in self.temp_dir.glob(f"*{ext}"):
                    f.unlink()
            print("🧹 Cleaned up temporary files")


# CLI for standalone testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PDF Compiler CLI")
    parser.add_argument("resume_json", help="Path to tailored resume JSON")
    parser.add_argument("--template", "-t", help="Template name", default="resume_template.tex")
    parser.add_argument("--output", "-o", help="Output filename (without .pdf)")
    parser.add_argument("--cleanup", action="store_true", help="Clean temp files after")
    
    args = parser.parse_args()
    
    compiler = PDFCompiler()
    
    pdf_path = compiler.compile_pdf(
        args.resume_json,
        template_name=args.template,
        output_name=args.output
    )
    
    if args.cleanup:
        compiler.cleanup_temp()
    
    if pdf_path:
        print(f"\n🎉 Resume ready: {pdf_path}")
