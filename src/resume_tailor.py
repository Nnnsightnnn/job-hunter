"""
Resume Tailor Module
Uses local Ollama LLM to rewrite resume bullets based on job descriptions
"""
import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import subprocess

# Ollama Python client - install with: pip install ollama
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


@dataclass
class TailoredResume:
    """Container for a tailored resume version"""
    job_id: str
    job_title: str
    company: str
    summary: str
    experience: list
    skills_highlighted: list
    created_at: str


class ResumeTailor:
    """
    Uses local LLM to tailor resume content to specific job descriptions
    """
    
    def __init__(
        self,
        master_resume_path: str = "data/master_resume.json",
        model: str = "llama3.1:8b",  # or mistral, gemma2, etc.
        ollama_host: str = "http://localhost:11434"
    ):
        self.master_resume_path = Path(master_resume_path)
        self.model = model
        self.ollama_host = ollama_host
        self.master_resume = self._load_master_resume()
        
    def _load_master_resume(self) -> dict:
        """Load the master resume JSON"""
        if not self.master_resume_path.exists():
            raise FileNotFoundError(f"Master resume not found: {self.master_resume_path}")
        
        with open(self.master_resume_path, 'r') as f:
            return json.load(f)
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return self.model.split(":")[0] in result.stdout
        except Exception:
            return False
    
    def _call_ollama(self, prompt: str, system: str = None) -> str:
        """Make a call to the local Ollama instance"""
        if OLLAMA_AVAILABLE:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system or "You are a professional resume writer."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response['message']['content']
        else:
            # Fallback to subprocess if ollama package not installed
            import subprocess
            cmd = ["ollama", "run", self.model, prompt]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout
    
    def extract_keywords(self, job_description: str) -> dict:
        """Extract key skills, requirements, and keywords from a job description"""
        
        prompt = f"""Analyze this job description and extract structured information.

JOB DESCRIPTION:
{job_description}

Respond ONLY with valid JSON in this exact format:
{{
    "required_skills": ["skill1", "skill2"],
    "preferred_skills": ["skill1", "skill2"],
    "key_responsibilities": ["resp1", "resp2"],
    "industry_keywords": ["keyword1", "keyword2"],
    "soft_skills": ["skill1", "skill2"],
    "experience_years": "X years",
    "education_requirements": "degree/certification",
    "company_values": ["value1", "value2"]
}}"""

        response = self._call_ollama(prompt)
        
        # Parse JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        return {"error": "Could not parse keywords", "raw_response": response}
    
    def tailor_bullet(
        self,
        original_bullet: str,
        job_keywords: dict,
        job_title: str,
        company: str
    ) -> str:
        """Rewrite a single resume bullet to match job requirements"""
        
        keywords_str = ", ".join(
            job_keywords.get("required_skills", []) +
            job_keywords.get("industry_keywords", [])
        )
        
        prompt = f"""Rewrite this resume bullet point to better match a {job_title} position at {company}.

ORIGINAL BULLET:
{original_bullet}

TARGET KEYWORDS TO INCORPORATE (where relevant):
{keywords_str}

RULES:
1. Keep the same core achievement/responsibility
2. Maintain or enhance any metrics/numbers
3. Naturally incorporate 1-2 relevant keywords if they fit
4. Use strong action verbs
5. Keep it to 1-2 lines max
6. Do NOT fabricate new achievements
7. Sound human, not robotic

Respond with ONLY the rewritten bullet point, nothing else."""

        response = self._call_ollama(prompt)
        
        # Clean up response
        bullet = response.strip()
        bullet = bullet.lstrip("•-*").strip()
        bullet = bullet.strip('"\'')
        
        return bullet
    
    def tailor_summary(
        self,
        job_description: str,
        job_title: str,
        company: str,
        job_keywords: dict
    ) -> str:
        """Generate a tailored professional summary"""
        
        original_summary = self.master_resume["personal"].get("summary", "")
        experience = self.master_resume.get("experience", [])
        skills = self.master_resume.get("skills", {})
        
        # Build context about the candidate
        years_exp = len(experience) * 2  # Rough estimate
        tech_skills = ", ".join(skills.get("technical", [])[:5])
        
        prompt = f"""Write a professional summary for a resume targeting this role:

ROLE: {job_title} at {company}

CANDIDATE BACKGROUND:
- Original summary: {original_summary}
- Years of experience: ~{years_exp}
- Key skills: {tech_skills}

KEY JOB REQUIREMENTS:
{json.dumps(job_keywords.get("required_skills", []), indent=2)}

RULES:
1. 2-3 sentences maximum
2. Lead with years of experience and main expertise
3. Include 2-3 relevant skills/keywords
4. End with value proposition for this specific role
5. Avoid buzzwords like "passionate" or "guru"
6. Sound confident but not arrogant

Respond with ONLY the summary paragraph, nothing else."""

        response = self._call_ollama(prompt)
        return response.strip().strip('"\'')
    
    def tailor_full_resume(
        self,
        job_id: str,
        job_title: str,
        company: str,
        job_description: str
    ) -> dict:
        """
        Create a fully tailored resume for a specific job
        
        Returns a dict with all resume sections tailored to the job
        """
        print(f"📝 Tailoring resume for: {job_title} at {company}")
        
        # Step 1: Extract keywords from JD
        print("   Analyzing job description...")
        keywords = self.extract_keywords(job_description)
        
        if "error" in keywords:
            print(f"   ⚠️  Warning: {keywords['error']}")
            keywords = {"required_skills": [], "industry_keywords": []}
        
        # Step 2: Tailor summary
        print("   Writing tailored summary...")
        tailored_summary = self.tailor_summary(
            job_description, job_title, company, keywords
        )
        
        # Step 3: Tailor experience bullets
        print("   Tailoring experience bullets...")
        tailored_experience = []
        
        for job in self.master_resume.get("experience", []):
            tailored_job = {
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "start_date": job["start_date"],
                "end_date": "Present" if job.get("current") else job["end_date"],
                "bullets": []
            }
            
            for bullet_data in job.get("bullets", []):
                original = bullet_data["original"]
                tailored = self.tailor_bullet(
                    original, keywords, job_title, company
                )
                tailored_job["bullets"].append(tailored)
            
            tailored_experience.append(tailored_job)
        
        # Step 4: Highlight relevant skills
        print("   Matching skills...")
        all_candidate_skills = (
            self.master_resume.get("skills", {}).get("technical", []) +
            self.master_resume.get("skills", {}).get("tools", []) +
            self.master_resume.get("skills", {}).get("soft", [])
        )
        
        required = set(s.lower() for s in keywords.get("required_skills", []))
        matched_skills = [s for s in all_candidate_skills if s.lower() in required]
        
        # Build final tailored resume
        tailored_resume = {
            "job_id": job_id,
            "job_title": job_title,
            "company": company,
            "personal": self.master_resume["personal"].copy(),
            "summary": tailored_summary,
            "experience": tailored_experience,
            "education": self.master_resume.get("education", []),
            "skills": self.master_resume.get("skills", {}),
            "skills_highlighted": matched_skills,
            "keywords_extracted": keywords,
            "created_at": __import__("datetime").datetime.now().isoformat()
        }
        
        # Update personal summary
        tailored_resume["personal"]["summary"] = tailored_summary
        
        print("   ✅ Resume tailored successfully!")
        
        return tailored_resume
    
    def save_tailored(self, tailored_resume: dict, output_dir: str = "output"):
        """Save tailored resume to JSON for PDF generation"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        company_slug = tailored_resume["company"].lower().replace(" ", "_")[:20]
        filename = f"resume_{company_slug}_{tailored_resume['job_id']}.json"
        
        filepath = output_path / filename
        with open(filepath, 'w') as f:
            json.dump(tailored_resume, f, indent=2)
        
        print(f"   📄 Saved: {filepath}")
        return filepath


# CLI for standalone testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Resume Tailor CLI")
    parser.add_argument("--jd", "-j", help="Job description text or file path", required=True)
    parser.add_argument("--title", "-t", help="Job title", required=True)
    parser.add_argument("--company", "-c", help="Company name", required=True)
    parser.add_argument("--model", "-m", help="Ollama model", default="llama3.1:8b")
    parser.add_argument("--resume", "-r", help="Master resume path", default="data/master_resume.json")
    
    args = parser.parse_args()
    
    # Load JD from file if path provided
    if Path(args.jd).exists():
        with open(args.jd, 'r') as f:
            jd_text = f.read()
    else:
        jd_text = args.jd
    
    tailor = ResumeTailor(
        master_resume_path=args.resume,
        model=args.model
    )
    
    result = tailor.tailor_full_resume(
        job_id="test_001",
        job_title=args.title,
        company=args.company,
        job_description=jd_text
    )
    
    tailor.save_tailored(result)
    
    print("\n📋 Tailored Summary:")
    print(result["summary"])
