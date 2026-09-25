# Inspected BLS source release

This records the package used for the BLS 4.0 assessment. It is not yet the
production seed lock. Check for BLS 4.1 before implementing the real import.

## Release

- Dataset: Bundeslebensmittelschlüssel, Version 4.0
- Publisher: Max Rubner-Institut
- Citation: Max Rubner-Institut (2025): *Bundeslebensmittelschlüssel (BLS),
  Version 4.0 — Deutsche Nährstoffdatenbank*. Karlsruhe.
- DOI: [10.25826/Data20251217-134202-0](https://doi.org/10.25826/Data20251217-134202-0)
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Official download page: <https://blsdb.de/download>
- Retrieved: 2026-09-25

## Package inventory

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `BLS_4_0_2025_DE.zip` | 14,263,306 | `12b7a6ba62807ec9b301eb276f897dc85f99b2292311618dec3749a12d984c91` |
| `BLS_4_0_Daten_2025_DE.xlsx` | 14,093,078 | `524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60` |
| `BLS_4_0_Components_DE_EN.xlsx` | 21,741 | `359aefcd2086f45e62ff3dbd0c8536306e594a5806ac325d8bf86f484561bdf4` |
| `BLS_4_0_Dokumentation_DE.pdf` | 469,803 | `6d83913f9b705399f86795a9c3afcb2d0454d1129bfb24ce53da911c5a6a24b6` |

## Repository policy

Do not commit the 14 MB source workbook merely for convenience. The official
release is reproducible from its download page and checksum. A later decision
may vendor a pinned source archive if builds must work without network access or
if the publisher does not provide stable historical downloads.

Any redistributed extract must retain the MRI attribution and identify that it
was transformed by this project. MRI has not reviewed or endorsed the result.
