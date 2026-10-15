from dataclasses import dataclass

from src.models.salary import format_salary


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

    @property
    def salary_text(self) -> str:
        return format_salary(self.salary_from, self.salary_to, self.salary_currency, self.salary_gross)
