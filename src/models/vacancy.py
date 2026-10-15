from dataclasses import dataclass


@dataclass(frozen=True)
class Vacancy:
    id: str
    name: str
    company: str
    salary_from: int | None
    salary_to: int | None
    salary_currency: str | None
    salary_gross: bool | None
    area: str
    experience: str
    employment: str
    work_format: str
    published_at: str
    url: str
