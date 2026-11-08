# Course submission

Based on the [Git submission guide](https://docs.google.com/document/d/12zH31_RhYnS6SasSdN8nZV-M_MSXaCOH70FLaj2zVzE/edit) and [connection diagram guide](https://docs.google.com/document/d/1KS7dq1E6zOfB5B8xyIxp4xSCyj1gk2xExZrP9ezTYGI/edit), reviewed 2026-11-08.

## Required artifacts

- [ ] Source for every deployed component, organized in separate directories.
- [ ] Root README: project description, team names, directory guide, tested library versions and hardware quantities.
- [ ] Final connection diagram showing actual components, ports, power and wiring; VCC red, GND black. Label wireless links separately.
- [ ] Final poster image embedded in the root README.
- [ ] Documented hardcoded parameters with their meaning and values.
- [ ] Blank secrets templates; real credentials excluded from Git.
- [ ] Runnable standalone sensor/device diagnostics in `Unit Tests/`.
- [ ] Final code on the required delivery branch. The guide names MASTER; confirm whether the current `main` is accepted.

The controller folder is named `raspberry_pi_hub/` for the team's selected hardware. The verified guides require component organization, not a specific Android package-folder depth. Preparing directories or templates does not complete an implementation deliverable.

Operating/calibration instructions, extra assets and a single repository are course recommendations. Fritzing and Schemdraw are suggested diagram tools, not mandatory formats.

## Published milestones

From the [Winter 2026–27 schedule](https://docs.google.com/spreadsheets/d/17Bb25aGqqGOJfwHxsIZI3TfVgzYnJR0O8yX0Nzit4x8/edit?gid=0). Times are Asia/Jerusalem; verify the assigned group slot in Moodle.

| Event | Date |
| --- | --- |
| SURFER seminar — Gamification | 2026-12-15, 13:30 |
| PoC, mandatory attendance | 2026-12-22, overall window 12:30–16:00 |
| Final demonstration, mandatory attendance | 2027-01-26, overall window 12:30–16:30; additional dates 2027-01-25 and 2027-01-28 |

## Unresolved requirements

The detailed project procedures, robustness guidance and mentoring checklist linked from the course hub were inaccessible. Obtain those documents before claiming complete course coverage. The exact PoC rubric, grading weights, seminar format and group demo slots remain unverified. Source links are retained in the local [source register](../agent_docs/SOURCES.md).

## Previous-semester examples

The [localization project](https://github.com/OhadElgamil/Localization_Project_IOT) groups controller code under `PI/`; [Smart Fridge](https://github.com/ibraheemak/Smart-Fridge) groups firmware under `ESP32/`; [Walkie-Talkie](https://github.com/MatanBiton/IOT-Walkie-Talkie) retains the course documentation and test folders. These are layout references from the supplied [project list](https://docs.google.com/spreadsheets/d/1q9qFeL9AefvToVv0LNbzaJhwoCWn06Mzk76VNzgOC6Y/edit?gid=1341237024), not evidence that every submission met the rubric.
