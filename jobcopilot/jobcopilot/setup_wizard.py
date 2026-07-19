"""Interactive setup wizard — builds profile.json and parses your CV.

Run:  python -m jobcopilot.setup_wizard
Re-runnable anytime; it pre-fills answers from an existing profile.json and
never touches your job history.
"""
from __future__ import annotations

from typing import Any

from . import config, resume_parser


def _ask(prompt: str, default: Any = "") -> str:
    suffix = f" [{default}]" if default not in ("", None, []) else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or (str(default) if default not in (None, []) else "")


def _ask_list(prompt: str, default: list[str]) -> list[str]:
    shown = ", ".join(default)
    val = input(f"{prompt} (comma-separated) [{shown}]: ").strip()
    if not val:
        return default
    return [x.strip() for x in val.split(",") if x.strip()]


def run() -> None:
    print("\n=== Job Application Copilot — setup ===\n")
    print("This builds profile.json (non-secret). Secrets go in .env separately.\n")

    p = config.load_profile()

    p["full_name"] = _ask("Full name", p["full_name"])
    p["current_title"] = _ask("Current job title", p["current_title"])
    yrs = _ask("Years of experience", p.get("years_experience") or "")
    p["years_experience"] = int(yrs) if yrs.isdigit() else p.get("years_experience")

    p["keywords"] = _ask_list("Skills / search keywords", p["keywords"])
    p["target_titles"] = _ask_list("Target job titles (ranked)", p["target_titles"])
    p["locations"] = _ask_list("Preferred locations", p["locations"])

    sal = _ask("Minimum salary (annual)", p.get("min_salary") or "")
    p["min_salary"] = int(sal) if sal.replace(",", "").isdigit() else p.get("min_salary")
    p["salary_currency"] = _ask("Salary currency", p["salary_currency"])
    p["notice_period"] = _ask("Notice period / availability", p["notice_period"])
    p["work_authorization"] = _ask("Work authorization status", p["work_authorization"])
    p["seniority"] = _ask("Seniority (entry/associate/mid/senior)", p["seniority"])

    p["industries_include"] = _ask_list("Industries to include", p["industries_include"])
    p["industries_exclude"] = _ask_list("Industries to exclude", p["industries_exclude"])
    p["companies_exclude"] = _ask_list("Companies to exclude (blocklist)", p["companies_exclude"])

    print("\nCommon screening answers (used to pre-fill application questions):")
    sa = p.get("screening_answers", {})
    sa["willing_to_relocate"] = _ask("  Willing to relocate?", sa.get("willing_to_relocate", ""))
    sa["requires_visa_sponsorship"] = _ask("  Require visa sponsorship?", sa.get("requires_visa_sponsorship", ""))
    sa["earliest_start_date"] = _ask("  Earliest start date?", sa.get("earliest_start_date", ""))
    p["screening_answers"] = sa

    thr = _ask("Match score threshold (0-100)", p.get("match_threshold", 70))
    p["match_threshold"] = int(thr) if str(thr).isdigit() else 70

    p["cv_path"] = _ask("Path to your CV (.docx)", p.get("cv_path", ""))

    config.save_profile(p)
    print(f"\nSaved profile to {config.PROFILE_PATH}")

    if p["cv_path"]:
        try:
            r = resume_parser.parse_and_cache(p["cv_path"])
            print(f"Parsed CV ({r.get('_source')}) — {len(r.get('skills', []))} skills cached.")
        except Exception as exc:
            print(f"Could not parse CV: {exc}")
            print("You can re-run the wizard or run: python -m jobcopilot.resume_parser <cv.docx>")

    print("\nNext steps:")
    print("  1. Copy .env.template to .env and add your ANTHROPIC_API_KEY.")
    print("  2. Start the copilot:  python -m jobcopilot.orchestrator")
    print("  3. Open the dashboard URL it prints (or add it to your iPad home screen).\n")


if __name__ == "__main__":
    run()
