# Judge Q&A

- **Why not regex only?** Candidate patterns will be followed by Verhoeff/Luhn/format validation.
- **Is it hardcoded?** The feature pipeline must process different synthetic inputs dynamically.
- **What is stored?** The design stores no uploaded documents or extracted PII.
- **What if OCR fails?** The UI will show an explicit warning and request a clearer image.
- **What are the limits?** The prototype targets supported, readable text and images; it is not perfect identity verification.
