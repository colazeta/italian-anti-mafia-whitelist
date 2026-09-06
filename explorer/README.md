# Data Explorer preview

This directory contains the versioned UI template for the project checkpoint Data Explorer.

The repository does **not** commit the real row-level Cosenza payload. The template is combined with validated parser outputs inside the private GitHub Actions workflow and emitted as a self-contained HTML artifact.

Two build modes exist:

- `sanitized`: source identifiers are masked and raw source blocks are omitted;
- `internal`: full row-level source observations are embedded, but the builder requires an explicit acknowledgement flag and the resulting file must remain an internal artifact.

The Explorer deliberately labels its row table as **source observations**. It must not visually or semantically present parser rows as canonical companies, registrations, removals or legal-effect states.
