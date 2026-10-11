# Python PDF Generator for Microsoft Copilot Cowork

This project is a Microsoft 365 app package containing one Copilot Cowork
Agent Skill. The skill uses Python and ReportLab to create styled PDFs from
Markdown or plain text.

## Structure

```text
pdf-generator/
├── manifest.json
├── color.png
├── outline.png
└── skills/
    └── pdf-generator/
        ├── SKILL.md
        ├── requirements.txt
        └── scripts/
            └── generate_pdf.py
```

The package follows the Microsoft Copilot Cowork plugin format using the
Microsoft 365 Unified App Manifest v1.28.

## Before production publishing

The developer URLs in `manifest.json` intentionally use `example.com`. Replace
the developer name, website, privacy policy, and terms-of-use URLs with the
publisher's real values before organizational deployment or store submission.

## Local validation

```powershell
python -m pip install -r .\skills\pdf-generator\requirements.txt
python -m unittest discover -s .\tests -v
python .\skills\pdf-generator\scripts\generate_pdf.py `
  --text "# Cowork PDF`n`nGenerated with Python." `
  --format markdown `
  --output .\sample.pdf
```

## Install in Cowork

For a personal skill, copy the `skills/pdf-generator` directory to:

```text
/Documents/Cowork/skills/pdf-generator/
```

For managed distribution, upload the generated app package ZIP through the
Microsoft 365 admin center. The ZIP root must contain `manifest.json`,
`color.png`, `outline.png`, and `skills/`.

To rebuild and validate the managed-distribution package with Microsoft 365
Agents Toolkit CLI 1.1.12 or later:

```powershell
atk package -f . `
  --manifest-file .\manifest.json `
  --output-package-file ..\pdf-generator-cowork.zip `
  --output-folder .\build `
  -i false
```

See the official Microsoft documentation:
https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development
