"""
Job Scraper Module
Uses JobSpy to aggregate jobs from LinkedIn, Indeed, Glassdoor, ZipRecruiter
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# JobSpy import - install with: pip install python-jobspy
try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False
    print("⚠️  JobSpy not installed. Run: pip install python-jobspy")


@dataclass
class JobListing:
    """Structured job listing data"""
    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    job_type: Optional[str] = None
    date_posted: Optional[str] = None
    source: str = ""
    scraped_at: str = ""
    status: str = "new"  # new, applied, interviewing, rejected, offer
    notes: str = ""
    
    def to_dict(self):
        return asdict(self)


class JobScraper:
    """
    Scrapes jobs from multiple sources and maintains a local database
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.jobs_file = self.data_dir / "jobs_database.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs = self._load_jobs()
    
    def _load_jobs(self) -> dict:
        """Load existing jobs from JSON database"""
        if self.jobs_file.exists():
            with open(self.jobs_file, 'r') as f:
                return json.load(f)
        return {"jobs": [], "last_updated": None}
    
    def _save_jobs(self):
        """Save jobs to JSON database"""
        self.jobs["last_updated"] = datetime.now().isoformat()
        with open(self.jobs_file, 'w') as f:
            json.dump(self.jobs, f, indent=2)
    
    def _generate_job_id(self, job: dict) -> str:
        """Generate unique ID for a job based on title, company, and URL"""
        unique_str = f"{job.get('title', '')}-{job.get('company', '')}-{job.get('job_url', '')}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def scrape(
        self,
        search_term: str,
        location: str = "Atlanta, GA",
        results_wanted: int = 20,
        hours_old: int = 72,
        sites: list = None,
        remote_only: bool = False,
        job_type: str = None  # fulltime, parttime, contract, internship
    ) -> list[JobListing]:
        """
        Scrape jobs from multiple sources
        
        Args:
            search_term: Job title or keywords to search
            location: City, State or "Remote"
            results_wanted: Max results per site
            hours_old: Only get jobs posted within X hours
            sites: List of sites ["indeed", "linkedin", "glassdoor", "zip_recruiter"]
            remote_only: Filter for remote jobs only
            job_type: Filter by job type
        
        Returns:
            List of JobListing objects
        """
        if not JOBSPY_AVAILABLE:
            raise ImportError("JobSpy is required. Install with: pip install python-jobspy")
        
        sites = sites or ["indeed", "linkedin", "glassdoor", "zip_recruiter"]
        
        print(f"🔍 Scraping jobs for: '{search_term}' in {location}")
        print(f"   Sites: {', '.join(sites)}")
        print(f"   Looking back: {hours_old} hours")
        
        try:
            jobs_df = scrape_jobs(
                site_name=sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                is_remote=remote_only,
                job_type=job_type,
                country_indeed="USA"
            )
            
            new_jobs = []
            for _, row in jobs_df.iterrows():
                job_id = self._generate_job_id(row.to_dict())
                
                # Skip if we already have this job
                existing_ids = [j["id"] for j in self.jobs["jobs"]]
                if job_id in existing_ids:
                    continue
                
                job = JobListing(
                    id=job_id,
                    title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=str(row.get("location", "")),
                    description=str(row.get("description", "")),
                    url=str(row.get("job_url", "")),
                    salary_min=row.get("min_amount"),
                    salary_max=row.get("max_amount"),
                    job_type=str(row.get("job_type", "")),
                    date_posted=str(row.get("date_posted", "")),
                    source=str(row.get("site", "")),
                    scraped_at=datetime.now().isoformat()
                )
                
                new_jobs.append(job)
                self.jobs["jobs"].append(job.to_dict())
            
            self._save_jobs()
            print(f"✅ Found {len(new_jobs)} new jobs (total: {len(self.jobs['jobs'])})")
            
            return new_jobs
            
        except Exception as e:
            print(f"❌ Scraping error: {e}")
            return []
    
    def search_saved(self, keyword: str = None, company: str = None, status: str = None) -> list[dict]:
        """Search through saved jobs"""
        results = self.jobs["jobs"]
        
        if keyword:
            keyword = keyword.lower()
            results = [
                j for j in results 
                if keyword in j["title"].lower() or keyword in j["description"].lower()
            ]
        
        if company:
            company = company.lower()
            results = [j for j in results if company in j["company"].lower()]
        
        if status:
            results = [j for j in results if j["status"] == status]
        
        return results
    
    def update_status(self, job_id: str, status: str, notes: str = None):
        """Update the status of a job application"""
        for job in self.jobs["jobs"]:
            if job["id"] == job_id:
                job["status"] = status
                if notes:
                    job["notes"] = notes
                self._save_jobs()
                return True
        return False
    
    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a specific job by ID"""
        for job in self.jobs["jobs"]:
            if job["id"] == job_id:
                return job
        return None
    
    def get_stats(self) -> dict:
        """Get statistics about saved jobs"""
        jobs = self.jobs["jobs"]
        return {
            "total": len(jobs),
            "by_status": {
                "new": len([j for j in jobs if j["status"] == "new"]),
                "applied": len([j for j in jobs if j["status"] == "applied"]),
                "interviewing": len([j for j in jobs if j["status"] == "interviewing"]),
                "rejected": len([j for j in jobs if j["status"] == "rejected"]),
                "offer": len([j for j in jobs if j["status"] == "offer"]),
            },
            "by_source": {},
            "last_updated": self.jobs.get("last_updated")
        }


# CLI for standalone testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Job Scraper CLI")
    parser.add_argument("--search", "-s", help="Search term", default="Project Manager")
    parser.add_argument("--location", "-l", help="Location", default="Atlanta, GA")
    parser.add_argument("--count", "-c", type=int, help="Results per site", default=10)
    parser.add_argument("--hours", type=int, help="Max hours old", default=72)
    parser.add_argument("--remote", action="store_true", help="Remote only")
    
    args = parser.parse_args()
    
    scraper = JobScraper(data_dir="data")
    jobs = scraper.scrape(
        search_term=args.search,
        location=args.location,
        results_wanted=args.count,
        hours_old=args.hours,
        remote_only=args.remote
    )
    
    print("\n📋 New Jobs Found:")
    for job in jobs[:5]:
        print(f"  • {job.title} at {job.company}")
        print(f"    {job.location} | {job.source}")
        print(f"    {job.url}\n")
