# Execution Breakdown Display Fix - Lite Summary

Fix two issues on the position detail page: (1) execution breakdown table showing empty rows despite successfully querying executions from the database, and (2) redundant "Total Quantity" metric in the position summary that duplicates "Peak Position Size".

## Key Points
- **Execution Display**: Data is queried correctly but template iteration produces empty rows due to data structure mismatch
- **Metrics Cleanup**: Remove redundant "Total Quantity" metric, keep only "Peak Position Size" when relevant
- **Test Target**: Position ID 35 with 7 executions for validation
