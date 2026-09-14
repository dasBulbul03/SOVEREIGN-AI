"""Build deterministic PDFs, coding ZIP, and manifest for presentation-v1.0.0."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
VERSION = "presentation-v1.0.0"
FIXED_ZIP_TIME = (2026, 9, 12, 0, 0, 0)


def write_pdf(path: Path, title: str, subtitle: str, pages: list[list[tuple[str, str]]]) -> None:
    doc = pymupdf.open()
    for page_number, blocks in enumerate(pages, start=1):
        page = doc.new_page(width=595, height=842)
        page.draw_rect((0, 0, 595, 78), color=(0.13, 0.36, 0.27), fill=(0.13, 0.36, 0.27))
        page.insert_text((44, 37), title, fontsize=19, color=(1, 1, 1), fontname="hebo")
        page.insert_text((44, 60), subtitle, fontsize=9, color=(0.86, 0.93, 0.89))
        y = 112
        for heading, body in blocks:
            page.insert_text((44, y), heading, fontsize=13, color=(0.13, 0.36, 0.27), fontname="hebo")
            y += 16
            used = page.insert_textbox(
                (44, y, 551, y + 150),
                body,
                fontsize=10.5,
                lineheight=1.35,
                color=(0.12, 0.15, 0.14),
            )
            if used < 0:
                raise RuntimeError(f"PDF block overflow in {path.name}: {heading}")
            y += max(58, 150 - used) + 18
        page.draw_line((44, 796), (551, 796), color=(0.73, 0.78, 0.75))
        page.insert_text((44, 816), "Aegis Process Systems Pvt. Ltd. | Synthetic presentation data", fontsize=8, color=(0.4, 0.45, 0.43))
        page.insert_text((510, 816), f"Page {page_number}", fontsize=8, color=(0.4, 0.45, 0.43))
    metadata = {"title": title, "author": "Aegis Process Systems Pvt. Ltd.", "subject": VERSION}
    doc.set_metadata(metadata)
    doc.save(
        path,
        garbage=4,
        deflate=True,
        clean=True,
        no_new_id=True,
        reproducible=True,
    )
    doc.close()


def build_pdfs() -> None:
    write_pdf(
        ROOT / "01-inspection/aegis-p101-inspection-report.pdf",
        "P-101 Condition Inspection",
        "Inspection reference IR-2026-0912 | 12 September 2026",
        [
            [
                ("Equipment and operating observation", "Equipment: P-101 centrifugal process pump. Service: cooling-water circulation. Inspection performed at 10:30 IST by Maya Rao, Maintenance Inspector. Pump remained in controlled operation during non-contact observation."),
                ("Measured condition", "Overall vibration at the drive-end bearing was 8.2 mm/s RMS. Discharge pressure was stable at 5.8 bar. A recurring liquid drip and wet patch were observed around the mechanical-seal area. No visible damage was observed on the coupling safety guard."),
                ("Immediate action", "The operator placed P-101 under enhanced observation and notified the maintenance manager. No casing, flange, seal, or guard was opened during this inspection."),
            ],
            [
                ("Requested decision", "Review the inspection evidence against the approved maintenance SOP. Decide whether maintenance work may proceed and identify all isolation, pressure-verification, authorization, and escalation controls."),
                ("Inspection limitation", "This is a visual and instrument-reading record, not proof of internal pump condition. Root cause, seal integrity, alignment, and bearing condition require responsible maintenance review after safe isolation."),
                ("Approval boundary", "Any generated recommendation is a draft. The maintenance manager remains accountable for work authorization, personnel safety, and verification of the physical plant state."),
            ],
        ],
    )
    write_pdf(
        ROOT / "01-inspection/aegis-pump-maintenance-sop.pdf",
        "P-101 Maintenance and Isolation SOP",
        "Controlled document APS-MNT-SOP-014 | Revision 3",
        [
            [
                ("1. Scope", "This procedure applies to planned or corrective maintenance on centrifugal pump P-101 and its mechanical seal, casing, coupling, or connected isolation boundary."),
                ("2. Safe shutdown and isolation", "Stop pump P-101 from the local control panel. Close suction valve V-14, then close discharge valve V-15. Apply lockout/tagout to the motor disconnect and both isolation valves. Record every lock and tag on the isolation certificate."),
                ("3. Depressurization", "Open drain valve DV-3 slowly. Verify the local pressure gauge reads zero bar before any casing, seal, flange, or connected fitting is loosened."),
            ],
            [
                ("4. Authorization", "The responsible maintenance technician and area operator must both inspect the isolation and sign the isolation certificate before the casing or seal area is opened. The maintenance manager authorizes the work after reviewing the inspection record."),
                ("5. Emergency stop-work rule", "If pressure does not fall to zero bar, stop work immediately. Do not loosen flanges or attempt maintenance. Escalate to the shift supervisor and verify the valve lineup against the current piping and instrumentation diagram."),
                ("6. Restart", "Confirm guards are installed, DV-3 is closed, and tools are cleared. Remove lockout/tagout under the two-person authorization rule. Open V-14 fully, vent trapped air, open V-15 to 25 percent, start P-101, and inspect for vibration or leakage before gradually opening V-15 fully."),
            ],
        ],
    )
    write_pdf(
        ROOT / "03-procurement/aegis-procurement-policy.pdf",
        "Maintenance Procurement Policy",
        "Controlled document APS-PROC-007 | Revision 2",
        [
            [
                ("1. Scope", "This policy governs comparison and recommendation of replacement parts used in maintenance work at Aegis Process Systems Pvt. Ltd."),
                ("2. Commercial controls", "Maximum budget: INR 50,000. Required currency: INR. Values from the original quotation must be preserved in the evaluation record."),
                ("3. Delivery control", "Maximum lead time: 14 days. Quotations with a longer delivery commitment require review and are not eligible for automatic recommendation."),
            ],
            [
                ("4. Warranty control", "Minimum warranty: 18 months. A shorter warranty requires review and is not eligible for automatic recommendation."),
                ("5. Recommendation rule", "Recommend the lowest evaluated total only among vendors that pass every stated budget, currency, delivery, and warranty control. A cheaper non-compliant offer must remain under review and must not be selected automatically."),
                ("6. Approval boundary", "The procurement manager must verify taxes, supplier eligibility, technical equivalence, signatures, and original quotations before issuing a purchase order. Decision-support output is not purchase authorization."),
            ],
        ],
    )


def build_zip() -> None:
    source = ROOT / "02-coding/repository"
    destination = ROOT / "02-coding/p101-temperature-monitor.zip"
    members = ["README.md", "monitor.py", "readings.csv", "test_monitor.py"]
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in members:
            path = source / name
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> None:
    paths = [
        ROOT / "01-inspection/aegis-p101-inspection-report.pdf",
        ROOT / "01-inspection/aegis-p101-seal-leak.jpg",
        ROOT / "01-inspection/aegis-pump-maintenance-sop.pdf",
        ROOT / "02-coding/p101-temperature-monitor.zip",
        ROOT / "03-procurement/mechanical-seal-quotations.csv",
        ROOT / "03-procurement/aegis-procurement-policy.pdf",
    ]
    destinations = {
        "aegis-p101-inspection-report.pdf": "workspace:01 Pump Inspection",
        "aegis-p101-seal-leak.jpg": "workspace:01 Pump Inspection",
        "aegis-pump-maintenance-sop.pdf": "knowledge:Maintenance SOPs",
        "p101-temperature-monitor.zip": "workspace:02 Controller Fix",
        "mechanical-seal-quotations.csv": "workspace:03 Pump Procurement",
        "aegis-procurement-policy.pdf": "workspace:03 Pump Procurement",
    }
    files = []
    for path in paths:
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "destination": destinations.get(path.name, f"workspace:{path.parent.name}"),
            }
        )
    manifest = {
        "dataset": VERSION,
        "organization": "Aegis Process Systems Pvt. Ltd.",
        "classification": "synthetic-safe-to-distribute",
        "files": files,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    build_pdfs()
    build_zip()
    build_manifest()
    print(f"Built {VERSION} with 6 versioned inputs")


if __name__ == "__main__":
    main()
