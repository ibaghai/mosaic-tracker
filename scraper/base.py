from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class JobPosting:
    title: str
    company: str
    external_id: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    url: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "external_id": self.external_id,
            "description": self.description,
            "location": self.location,
            "department": self.department,
            "employment_type": self.employment_type,
            "url": self.url,
            "scraped_at": self.scraped_at,
        }
