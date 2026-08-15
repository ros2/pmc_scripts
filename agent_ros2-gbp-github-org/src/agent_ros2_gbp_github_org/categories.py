"""Issue categories for ros2-gbp-github-org issues."""

from enum import Enum


class IssueCategory(str, Enum):
    NewReleaseRepository = "NewReleaseRepository"
    NewReleaseTeam = "NewReleaseTeam"
    UpdateReleaseTeamMembership = "UpdateReleaseTeamMembership"
    UnknownCategory = "UnknownCategory"

    def __str__(self) -> str:
        return self.value


NewReleaseRepository = IssueCategory.NewReleaseRepository
NewReleaseTeam = IssueCategory.NewReleaseTeam
UpdateReleaseTeamMembership = IssueCategory.UpdateReleaseTeamMembership
UnknownCategory = IssueCategory.UnknownCategory
UknownCategory = UnknownCategory  # Alias for common typo

__all__ = [
    "IssueCategory",
    "NewReleaseRepository",
    "NewReleaseTeam",
    "UpdateReleaseTeamMembership",
    "UnknownCategory",
    "UknownCategory",
]
