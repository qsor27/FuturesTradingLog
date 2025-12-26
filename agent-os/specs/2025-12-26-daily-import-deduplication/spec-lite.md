# Spec Summary (Lite)

Ensure the scheduled daily import runs exactly once per market close by tracking import state in Redis. Skip weekends automatically and allow manual imports to bypass deduplication. Prevents duplicate processing from container restarts or scheduler issues.
