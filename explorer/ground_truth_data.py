"""Hand-labeled yes/no answers for each (candidate, rubric question) pair.

Used by the experiment page to score classification predictions against a
known-correct answer. Only the five fixed CLASSIFICATION_QUESTIONS keys have
labels here - custom questions have no ground truth and are out of scope for
that page.

Labels are derived by reading the fictional resumes in module3/ against each
job requirement:

- Dr. Elena Martinez: CTO and prior VP Engineering with 18 years in tech
  leadership, HIPAA-regulated healthcare analytics, AWS Certified Solutions
  Architect. Qualifies on every rubric question.
- Marcus Reed: Engineering Manager since 2022 with 8 years total experience -
  well short of the 10-year leadership and 5-year team-management bars, and
  has never held a VP/CTO title. He does build software for medical
  practices (healthcare technology experience) and has hands-on AWS
  deployment experience, so those two are yes.
- Olivia Grant: hospitality and events background with no technology,
  healthcare, or cloud experience at all. No on every rubric question.
"""

GROUND_TRUTH = {
    "elena-martinez": {
        "leadership_10yr": True,
        "team_management_5yr": True,
        "healthcare_hipaa": True,
        "cloud_infra": True,
        "executive_experience": True,
    },
    "marcus-reed": {
        "leadership_10yr": False,
        "team_management_5yr": False,
        "healthcare_hipaa": True,
        "cloud_infra": True,
        "executive_experience": False,
    },
    "olivia-grant": {
        "leadership_10yr": False,
        "team_management_5yr": False,
        "healthcare_hipaa": False,
        "cloud_infra": False,
        "executive_experience": False,
    },
}
