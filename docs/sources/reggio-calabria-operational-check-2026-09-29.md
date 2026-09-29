# Reggio Calabria White List — source qualification checkpoint (29 September 2026)

## Scope

This checkpoint qualifies the current ordinary White List publication surface for the Prefettura di Reggio Calabria without promoting it to reviewed source/parser coverage. The two mandatory logical populations are independently evidenced on the official landing page:

- **listed** — the attachment labelled as the list of suppliers/service providers not subject to attempted mafia infiltration;
- **applicant** — the attachment labelled as companies requesting registration.

Landing page: https://prefettura.interno.gov.it/it/prefetture/reggio-calabria/evidenza/white-list

## Archive-first evidence

The scheduled national Prefecture robot run on 29 September 2026 completed successfully and captured the landing page plus both current PDFs through the governed evidence archive. The report contained no errors and no pending frontier for Reggio Calabria.

Workflow run: https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/36557477529

| population | current resource | SHA-256 | bytes | HTTP last-modified |
| --- | --- | --- | ---: | --- |
| listed | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-foglio-unico-nuove-attivita-24-set-2026.pdf | `f93a63a89c2c22f9fee27af29654c3dd5e97b58452dde92224b4b2259d3f148f` | 266878 | 24 Sep 2026 15:15:23 GMT |
| applicant | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-richieste-iscrizioni-white-list-foglio-del-24-set-2026.pdf | `da60df92f7ffdfc1148ead109395e00ae34e11cb53c01ccc6928bbdff0c71d53` | 372194 | 24 Sep 2026 15:15:07 GMT |

The attachment names and source presentation support 24 September 2026 as the current edition label. Capture time remains distinct from source-reference time and no legal-effect date is inferred from either value.

## Population semantics

The applicant PDF is not being inferred from a filename alone: the official landing page explicitly describes it as the list of companies requesting registration. The other attachment is separately presented as the White List of registered suppliers/service providers. This satisfies source discovery for both mandatory logical populations, but **does not yet satisfy parser validation**.

## Remaining gate

`population_mapping_reviewed` must remain `false` until both exact byte-pinned PDFs have been parsed and reviewed end-to-end. The next executable step is:

1. extract both archived PDFs using a scope-local or demonstrably compatible parser family;
2. establish finite row/page/status/identifier invariants and physical locators;
3. add focused regression tests;
4. bind `reggio-calabria-listed` and `reggio-calabria-applicants` to the validated parser(s);
5. only then set the robot mapping to reviewed and run the national/public candidate gates.

Accordingly this checkpoint increases qualified source discovery but deliberately records **reviewed Prefettura coverage +0** until the parser gate is closed.
