#!/usr/bin/env python3
"""
Job Hunter - Web UI
A simple, friendly web interface for job searching and resume tailoring.

Run: python app.py
Then open: http://localhost:5050
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from job_scraper import JobScraper
from resume_tailor import ResumeTailor
from pdf_compiler import PDFCompiler

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize components
DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

scraper = JobScraper(data_dir=str(DATA_DIR))
tailor = ResumeTailor(master_resume_path=str(DATA_DIR / "master_resume.json"))
compiler = PDFCompiler(output_dir=str(OUTPUT_DIR))


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def home():
    """Dashboard home page"""
    stats = scraper.get_stats()
    recent_jobs = scraper.search_saved()[:5]
    
    # Check for recent PDFs
    recent_pdfs = sorted(OUTPUT_DIR.glob("*.pdf"), key=os.path.getmtime, reverse=True)[:3]
    
    return render_template("home.html", 
                         stats=stats, 
                         recent_jobs=recent_jobs,
                         recent_pdfs=[p.name for p in recent_pdfs])


@app.route("/search", methods=["GET", "POST"])
def search():
    """Search for new jobs"""
    if request.method == "POST":
        search_term = request.form.get("search_term", "").strip()
        location = request.form.get("location", "Atlanta, GA").strip()
        remote_only = request.form.get("remote_only") == "on"
        
        if not search_term:
            flash("Please enter a job title to search for.", "error")
            return redirect(url_for("search"))
        
        try:
            jobs = scraper.scrape(
                search_term=search_term,
                location=location,
                results_wanted=20,
                hours_old=72,
                remote_only=remote_only
            )
            
            if jobs:
                flash(f"Found {len(jobs)} new jobs!", "success")
            else:
                flash("No new jobs found. Try different keywords.", "info")
                
        except Exception as e:
            flash(f"Search error: {str(e)}", "error")
        
        return redirect(url_for("jobs"))
    
    return render_template("search.html")


@app.route("/jobs")
def jobs():
    """Browse all saved jobs"""
    status_filter = request.args.get("status", "")
    keyword = request.args.get("keyword", "")
    
    all_jobs = scraper.search_saved(
        status=status_filter if status_filter else None,
        keyword=keyword if keyword else None
    )
    
    stats = scraper.get_stats()
    
    return render_template("jobs.html", 
                         jobs=all_jobs, 
                         stats=stats,
                         current_status=status_filter,
                         current_keyword=keyword)


@app.route("/job/<job_id>")
def job_detail(job_id):
    """View a single job's details"""
    job = scraper.get_job(job_id)
    
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("jobs"))
    
    # Check if we have a tailored resume for this job
    tailored_json = list(OUTPUT_DIR.glob(f"*{job_id}*.json"))
    tailored_pdf = list(OUTPUT_DIR.glob(f"*{job_id}*.pdf"))
    
    return render_template("job_detail.html", 
                         job=job,
                         has_tailored_json=len(tailored_json) > 0,
                         has_tailored_pdf=len(tailored_pdf) > 0,
                         pdf_name=tailored_pdf[0].name if tailored_pdf else None)


@app.route("/job/<job_id>/tailor", methods=["POST"])
def tailor_resume(job_id):
    """Tailor resume for a specific job"""
    job = scraper.get_job(job_id)
    
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("jobs"))
    
    try:
        flash("Tailoring resume... This takes about 30-60 seconds.", "info")
        
        tailored = tailor.tailor_full_resume(
            job_id=job['id'],
            job_title=job['title'],
            company=job['company'],
            job_description=job['description']
        )
        
        tailor.save_tailored(tailored, str(OUTPUT_DIR))
        
        flash(f"Resume tailored for {job['company']}!", "success")
        
    except Exception as e:
        flash(f"Tailoring error: {str(e)}. Is Ollama running?", "error")
    
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/job/<job_id>/generate-pdf", methods=["POST"])
def generate_pdf(job_id):
    """Generate PDF from tailored resume"""
    job = scraper.get_job(job_id)
    
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("jobs"))
    
    # Find the tailored JSON
    tailored_files = list(OUTPUT_DIR.glob(f"*{job_id}*.json"))
    
    if not tailored_files:
        flash("Please tailor the resume first.", "error")
        return redirect(url_for("job_detail", job_id=job_id))
    
    try:
        pdf_path = compiler.compile_pdf(str(tailored_files[0]))
        
        if pdf_path:
            compiler.cleanup_temp()
            scraper.update_status(job_id, "applied")
            flash(f"PDF generated! Status updated to 'Applied'.", "success")
        else:
            flash("PDF generation failed. Check LaTeX installation.", "error")
            
    except Exception as e:
        flash(f"PDF error: {str(e)}", "error")
    
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/job/<job_id>/full-process", methods=["POST"])
def full_process(job_id):
    """One-click: tailor + generate PDF"""
    job = scraper.get_job(job_id)
    
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("jobs"))
    
    try:
        # Step 1: Tailor
        tailored = tailor.tailor_full_resume(
            job_id=job['id'],
            job_title=job['title'],
            company=job['company'],
            job_description=job['description']
        )
        
        # Step 2: Generate PDF
        pdf_path = compiler.compile_from_dict(tailored)
        
        if pdf_path:
            compiler.cleanup_temp()
            scraper.update_status(job_id, "applied")
            flash(f"Resume ready for {job['company']}! Click Download below.", "success")
        else:
            # Still save the JSON even if PDF fails
            tailor.save_tailored(tailored, str(OUTPUT_DIR))
            flash("Resume tailored but PDF failed. Check LaTeX.", "warning")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/job/<job_id>/update-status", methods=["POST"])
def update_status(job_id):
    """Update job application status"""
    new_status = request.form.get("status")
    notes = request.form.get("notes", "")
    
    if new_status in ["new", "applied", "interviewing", "rejected", "offer"]:
        scraper.update_status(job_id, new_status, notes)
        flash(f"Status updated to: {new_status}", "success")
    
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/download/<filename>")
def download_file(filename):
    """Download a generated PDF"""
    file_path = OUTPUT_DIR / filename
    
    if file_path.exists() and filename.endswith(".pdf"):
        return send_file(file_path, as_attachment=True)
    
    flash("File not found.", "error")
    return redirect(url_for("home"))


@app.route("/resumes")
def resumes():
    """View all generated resumes"""
    pdfs = sorted(OUTPUT_DIR.glob("*.pdf"), key=os.path.getmtime, reverse=True)
    jsons = sorted(OUTPUT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    
    resume_files = []
    for pdf in pdfs:
        # Extract job info from filename
        parts = pdf.stem.split("_")
        resume_files.append({
            "name": pdf.name,
            "company": parts[1] if len(parts) > 1 else "Unknown",
            "date": datetime.fromtimestamp(pdf.stat().st_mtime).strftime("%b %d, %Y"),
            "size": f"{pdf.stat().st_size / 1024:.1f} KB"
        })
    
    return render_template("resumes.html", resumes=resume_files)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    """Edit master resume"""
    resume_path = DATA_DIR / "master_resume.json"
    
    if request.method == "POST":
        try:
            # Get form data and update resume
            with open(resume_path, 'r') as f:
                resume = json.load(f)
            
            # Update personal info
            resume["personal"]["name"] = request.form.get("name", "")
            resume["personal"]["email"] = request.form.get("email", "")
            resume["personal"]["phone"] = request.form.get("phone", "")
            resume["personal"]["location"] = request.form.get("location", "")
            resume["personal"]["linkedin"] = request.form.get("linkedin", "")
            resume["personal"]["summary"] = request.form.get("summary", "")
            
            # Update skills
            resume["skills"]["technical"] = [s.strip() for s in request.form.get("technical_skills", "").split(",") if s.strip()]
            resume["skills"]["soft"] = [s.strip() for s in request.form.get("soft_skills", "").split(",") if s.strip()]
            resume["skills"]["tools"] = [s.strip() for s in request.form.get("tools", "").split(",") if s.strip()]
            
            resume["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            
            with open(resume_path, 'w') as f:
                json.dump(resume, f, indent=2)
            
            flash("Profile saved!", "success")
            
        except Exception as e:
            flash(f"Error saving: {str(e)}", "error")
        
        return redirect(url_for("profile"))
    
    # Load current resume
    with open(resume_path, 'r') as f:
        resume = json.load(f)
    
    return render_template("profile.html", resume=resume)


@app.route("/experience", methods=["GET", "POST"])
def experience():
    """Edit work experience"""
    resume_path = DATA_DIR / "master_resume.json"
    
    with open(resume_path, 'r') as f:
        resume = json.load(f)
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            new_exp = {
                "id": f"exp_{len(resume['experience']) + 1:03d}",
                "company": request.form.get("company", ""),
                "title": request.form.get("title", ""),
                "location": request.form.get("exp_location", ""),
                "start_date": request.form.get("start_date", ""),
                "end_date": request.form.get("end_date", ""),
                "current": request.form.get("current") == "on",
                "bullets": []
            }
            
            # Parse bullets
            bullets_text = request.form.get("bullets", "")
            for line in bullets_text.strip().split("\n"):
                if line.strip():
                    new_exp["bullets"].append({
                        "id": f"bullet_{len(new_exp['bullets']) + 1:03d}",
                        "original": line.strip().lstrip("•-* "),
                        "keywords": [],
                        "metrics": {},
                        "tailored_versions": {}
                    })
            
            resume["experience"].insert(0, new_exp)
            
            with open(resume_path, 'w') as f:
                json.dump(resume, f, indent=2)
            
            flash("Experience added!", "success")
        
        elif action == "delete":
            exp_id = request.form.get("exp_id")
            resume["experience"] = [e for e in resume["experience"] if e["id"] != exp_id]
            
            with open(resume_path, 'w') as f:
                json.dump(resume, f, indent=2)
            
            flash("Experience removed.", "success")
        
        return redirect(url_for("experience"))
    
    return render_template("experience.html", experience=resume.get("experience", []))


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    flash("Page not found.", "error")
    return redirect(url_for("home"))


@app.errorhandler(500)
def server_error(e):
    flash("Something went wrong. Please try again.", "error")
    return redirect(url_for("home"))


# ============================================================================
# TEMPLATE FILTERS
# ============================================================================

@app.template_filter("truncate_text")
def truncate_text(text, length=100):
    if len(text) <= length:
        return text
    return text[:length] + "..."


@app.template_filter("format_date")
def format_date(date_str):
    if not date_str or date_str.lower() == "present":
        return "Present"
    try:
        if len(date_str) == 7:
            dt = datetime.strptime(date_str, "%Y-%m")
            return dt.strftime("%b %Y")
    except:
        pass
    return date_str


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  🎯 Job Hunter")
    print("  Open in browser: http://localhost:5050")
    print("=" * 50 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5050)
