# Selected publication monitoring

`data/monitoring/national_coverage.json` now records the exact selected public release and the selected source dates/hashes/populations per authority. Previously, several date fields still reflected September despite the published Catania, Perugia and Alessandria updates.

Regenerate from the actual selected immutable registry with:

```
python -m white_list_archive.acquisition.published_monitoring --registry /path/to/verified/registry.json
```

The synchroniser checks the registry's full SHA-256 and byte length against `data/publication/public_snapshot.json` before reading metadata. It reconciles record/source/authority denominators and rejects duplicate or missing source identities. It never derives dates from robot timestamps or prospective parser configuration. Counts are source-document presences, not deduplicated businesses.

Every selector PR must regenerate monitoring against its exact selected derivative. CI verifies release tag, registry SHA and the national sum, preventing a future selector change from silently leaving this ledger on an older release. Authorities absent from the selected public release have zero selected observations and no selected reference date; they are not declared complete. Capture, canonical, monitoring and edition-attribution stages remain unchanged. Independently known later source dates are preserved, so publication cannot erase a known freshness gap.

The ledger makes no live-deployment assertion: `live_deployment_verified` remains unknown. Live acceptance is separately proved by the sole publisher's successful post-deployment five-file hash/size readback. For the Alessandria release `public-data-43524455108-1`, this succeeded in [run43525691442](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43525691442), deploy job132231544321. All-source freshness remains explicitly unverified; the national newest date does not certify the other source series.
