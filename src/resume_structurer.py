"""
Resume Structurer Module
Uses local Ollama LLM to extract and structure resume data from raw text
"""
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# Ollama Python client
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class ResumeStructurer:
    """
    Uses local LLM to structure resume text into the master_resume format
    """

    def __init__(
        self,
        master_resume_path: str = "data/master_resume.json",
        model: str = "llama3.1:8b",
        ollama_host: str = "http://localhost:11434"
    ):
        self.master_resume_path = Path(master_resume_path)
        self.model = model
        self.ollama_host = ollama_host

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
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system or "You are a helpful assistant that extracts structured data from resumes."},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response['message']['content']
            except Exception as e:
                raise RuntimeError(f"Ollama error: {str(e)}")
        else:
            # Fallback to subprocess
            try:
                cmd = ["ollama", "run", self.model, prompt]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                return result.stdout
            except Exception as e:
                raise RuntimeError(f"Ollama subprocess error: {str(e)}")

    def _extract_json(self, response: str) -> Optional[dict]:
        """Extract JSON from LLM response"""
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return None

    def extract_personal_info(self, resume_text: str) -> dict:
        """Extract personal/contact information from resume text"""
        prompt = f"""Extract contact information from this resume. Return ONLY valid JSON.

RESUME TEXT:
{resume_text[:3000]}

Return JSON in this exact format (use empty strings if not found):
{{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "(555) 555-5555",
    "location": "City, State",
    "linkedin": "linkedin.com/in/profile",
    "summary": "Professional summary if present"
}}"""

        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            if data:
                return {
                    "name": data.get("name", ""),
                    "email": data.get("email", ""),
                    "phone": data.get("phone", ""),
                    "location": data.get("location", ""),
                    "linkedin": data.get("linkedin", ""),
                    "summary": data.get("summary", "")
                }
        except Exception:
            pass

        return self._regex_extract_personal(resume_text)

    def _regex_extract_personal(self, text: str) -> dict:
        """Fallback regex extraction for personal info"""
        result = {
            "name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "summary": ""
        }

        # Email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            result["email"] = email_match.group()

        # Phone
        phone_match = re.search(r'[\(]?\d{3}[\)]?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        if phone_match:
            result["phone"] = phone_match.group()

        # LinkedIn
        linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', text, re.IGNORECASE)
        if linkedin_match:
            result["linkedin"] = linkedin_match.group()

        # Name - usually first line or first notable text
        lines = text.strip().split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and len(line) < 50 and not '@' in line and not line[0].isdigit():
                result["name"] = line
                break

        return result

    def extract_experience(self, resume_text: str) -> list:
        """Extract work experience from resume text"""
        prompt = f"""Extract work experience from this resume. Return ONLY valid JSON.

RESUME TEXT:
{resume_text}

Return JSON array in this format:
[
    {{
        "company": "Company Name",
        "title": "Job Title",
        "location": "City, State",
        "start_date": "YYYY-MM",
        "end_date": "YYYY-MM or present",
        "current": true or false,
        "bullets": ["Achievement 1", "Achievement 2"]
    }}
]

If no experience found, return empty array: []"""

        try:
            response = self._call_ollama(prompt)

            # Try to extract array
            array_match = re.search(r'\[[\s\S]*\]', response)
            if array_match:
                data = json.loads(array_match.group())
                if isinstance(data, list):
                    return self._format_experience(data)
        except Exception:
            pass

        return []

    def _format_experience(self, experience_list: list) -> list:
        """Format experience data to match master_resume schema"""
        formatted = []

        for i, exp in enumerate(experience_list):
            bullets = []
            for j, bullet in enumerate(exp.get("bullets", [])):
                if isinstance(bullet, str):
                    bullets.append({
                        "id": f"bullet_{j+1:03d}",
                        "original": bullet.strip().lstrip("•-* "),
                        "keywords": [],
                        "metrics": {},
                        "tailored_versions": {}
                    })

            is_current = exp.get("current", False)
            if not is_current and exp.get("end_date", "").lower() == "present":
                is_current = True

            formatted.append({
                "id": f"exp_{i+1:03d}",
                "company": exp.get("company", ""),
                "title": exp.get("title", ""),
                "location": exp.get("location", ""),
                "start_date": exp.get("start_date", ""),
                "end_date": "present" if is_current else exp.get("end_date", ""),
                "current": is_current,
                "bullets": bullets
            })

        return formatted

    def extract_education(self, resume_text: str) -> list:
        """Extract education from resume text"""
        prompt = f"""Extract education from this resume. Return ONLY valid JSON.

RESUME TEXT:
{resume_text}

Return JSON array in this format:
[
    {{
        "institution": "University Name",
        "degree": "Bachelor of Science",
        "field": "Computer Science",
        "graduation_date": "YYYY-MM"
    }}
]

If no education found, return empty array: []"""

        try:
            response = self._call_ollama(prompt)

            array_match = re.search(r'\[[\s\S]*\]', response)
            if array_match:
                data = json.loads(array_match.group())
                if isinstance(data, list):
                    return self._format_education(data)
        except Exception:
            pass

        return []

    def _format_education(self, education_list: list) -> list:
        """Format education data to match master_resume schema"""
        formatted = []

        for edu in education_list:
            formatted.append({
                "institution": edu.get("institution", ""),
                "degree": edu.get("degree", ""),
                "field": edu.get("field", ""),
                "graduation_date": edu.get("graduation_date", ""),
                "gpa": edu.get("gpa", ""),
                "honors": edu.get("honors", []),
                "relevant_coursework": edu.get("relevant_coursework", [])
            })

        return formatted

    def extract_skills(self, resume_text: str) -> dict:
        """Extract skills from resume text"""
        prompt = f"""Extract skills from this resume. Categorize them. Return ONLY valid JSON.

RESUME TEXT:
{resume_text}

Return JSON in this format:
{{
    "technical": ["Python", "SQL", "AWS"],
    "soft": ["Leadership", "Communication"],
    "tools": ["Excel", "Jira", "Git"]
}}

If no skills found, return empty arrays."""

        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            if data:
                return {
                    "technical": data.get("technical", []),
                    "soft": data.get("soft", []),
                    "tools": data.get("tools", []),
                    "certifications": data.get("certifications", [])
                }
        except Exception:
            pass

        return {
            "technical": [],
            "soft": [],
            "tools": [],
            "certifications": []
        }

    def structure_resume(self, resume_text: str, use_ai: bool = True) -> Tuple[dict, Optional[str]]:
        """
        Full resume structuring - extract all sections

        Returns:
            Tuple of (structured_data, error_message)
        """
        if not use_ai:
            # Basic extraction without AI
            personal = self._regex_extract_personal(resume_text)
            return {
                "personal": personal,
                "experience": [],
                "education": [],
                "skills": {"technical": [], "soft": [], "tools": [], "certifications": []},
                "raw_text": resume_text
            }, "AI structuring disabled. Only basic extraction performed."

        if not self._check_ollama():
            # Fallback when Ollama not available
            personal = self._regex_extract_personal(resume_text)
            return {
                "personal": personal,
                "experience": [],
                "education": [],
                "skills": {"technical": [], "soft": [], "tools": [], "certifications": []},
                "raw_text": resume_text
            }, "Ollama not available. Only basic extraction performed."

        try:
            print("   Extracting personal info...")
            personal = self.extract_personal_info(resume_text)

            print("   Extracting experience...")
            experience = self.extract_experience(resume_text)

            print("   Extracting education...")
            education = self.extract_education(resume_text)

            print("   Extracting skills...")
            skills = self.extract_skills(resume_text)

            return {
                "personal": personal,
                "experience": experience,
                "education": education,
                "skills": skills
            }, None

        except Exception as e:
            # Return partial results with error
            personal = self._regex_extract_personal(resume_text)
            return {
                "personal": personal,
                "experience": [],
                "education": [],
                "skills": {"technical": [], "soft": [], "tools": [], "certifications": []},
                "raw_text": resume_text
            }, f"AI extraction failed: {str(e)}"

    def merge_with_master(
        self,
        extracted_data: dict,
        master_data: dict,
        mode: str = "merge"
    ) -> dict:
        """
        Merge extracted data with master resume

        Modes:
            - replace: Overwrite all existing data
            - merge: Update personal info, add new experience/education, dedupe skills
            - append: Only add entries that don't exist
        """
        if mode == "replace":
            return self._create_full_resume(extracted_data)

        elif mode == "append":
            result = master_data.copy()

            # Add new experience entries only
            existing_exp = {(e["company"], e["title"], e["start_date"]) for e in result.get("experience", [])}
            for exp in extracted_data.get("experience", []):
                key = (exp["company"], exp["title"], exp["start_date"])
                if key not in existing_exp:
                    result.setdefault("experience", []).insert(0, exp)

            # Add new education entries only
            existing_edu = {(e["institution"], e["degree"]) for e in result.get("education", [])}
            for edu in extracted_data.get("education", []):
                key = (edu["institution"], edu["degree"])
                if key not in existing_edu:
                    result.setdefault("education", []).append(edu)

            # Add new skills only
            for category in ["technical", "soft", "tools", "certifications"]:
                existing = set(s.lower() for s in result.get("skills", {}).get(category, []))
                for skill in extracted_data.get("skills", {}).get(category, []):
                    if skill.lower() not in existing:
                        result.setdefault("skills", {}).setdefault(category, []).append(skill)

            return result

        else:  # merge (default)
            result = master_data.copy()

            # Update personal info with non-empty values
            for key, value in extracted_data.get("personal", {}).items():
                if value and value.strip():
                    result.setdefault("personal", {})[key] = value

            # Add new experience entries
            existing_exp = {(e["company"], e["title"], e["start_date"]) for e in result.get("experience", [])}
            for exp in extracted_data.get("experience", []):
                key = (exp["company"], exp["title"], exp["start_date"])
                if key not in existing_exp:
                    result.setdefault("experience", []).insert(0, exp)

            # Add new education entries
            existing_edu = {(e["institution"], e["degree"]) for e in result.get("education", [])}
            for edu in extracted_data.get("education", []):
                key = (edu["institution"], edu["degree"])
                if key not in existing_edu:
                    result.setdefault("education", []).append(edu)

            # Merge skills (union, deduplicated)
            for category in ["technical", "soft", "tools", "certifications"]:
                existing = result.get("skills", {}).get(category, [])
                new_skills = extracted_data.get("skills", {}).get(category, [])

                existing_lower = {s.lower() for s in existing}
                for skill in new_skills:
                    if skill.lower() not in existing_lower:
                        existing.append(skill)
                        existing_lower.add(skill.lower())

                result.setdefault("skills", {})[category] = existing

            return result

    def _create_full_resume(self, extracted_data: dict) -> dict:
        """Create a complete master_resume structure from extracted data"""
        return {
            "meta": {
                "version": "1.0",
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "notes": "Imported from uploaded resume"
            },
            "personal": {
                "name": extracted_data.get("personal", {}).get("name", ""),
                "email": extracted_data.get("personal", {}).get("email", ""),
                "phone": extracted_data.get("personal", {}).get("phone", ""),
                "location": extracted_data.get("personal", {}).get("location", ""),
                "linkedin": extracted_data.get("personal", {}).get("linkedin", ""),
                "portfolio": "",
                "summary": extracted_data.get("personal", {}).get("summary", "")
            },
            "experience": extracted_data.get("experience", []),
            "education": extracted_data.get("education", []),
            "skills": {
                "technical": extracted_data.get("skills", {}).get("technical", []),
                "soft": extracted_data.get("skills", {}).get("soft", []),
                "tools": extracted_data.get("skills", {}).get("tools", []),
                "certifications": extracted_data.get("skills", {}).get("certifications", [])
            },
            "projects": [],
            "volunteer": [],
            "awards": []
        }

    def save_master_resume(self, resume_data: dict, path: str = None) -> str:
        """Save the merged resume to master_resume.json"""
        save_path = Path(path) if path else self.master_resume_path

        # Update metadata
        resume_data.setdefault("meta", {})["last_updated"] = datetime.now().strftime("%Y-%m-%d")

        with open(save_path, 'w') as f:
            json.dump(resume_data, f, indent=2)

        return str(save_path)
