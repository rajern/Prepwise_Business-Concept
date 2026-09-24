# Production observability

Prepwise sends backend OpenTelemetry to the existing workspace-based Application Insights
resource. The Azure Monitor Python distribution instruments FastAPI and supported outbound HTTP
clients. SQLAlchemy is instrumented explicitly so PostgreSQL calls to Neon appear as dependency
spans. Neon platform monitoring remains separate from application-side dependency telemetry.

The production Container App receives `APPLICATIONINSIGHTS_CONNECTION_STRING` from Bicep. Local
development leaves it empty, so telemetry export is disabled. Application logs continue to use the
structured JSON format written to Container Apps and Log Analytics. Request logs include the
application request ID and, when telemetry is active, the OpenTelemetry trace ID.

Exception telemetry is deliberately sanitised: traces record the exception type and error status,
not the runtime exception message, credentials, query parameters or request bodies.

## Operational signals

Application Insights exposes the four Milestone 1 monitoring signals:

* availability: the three-region standard web test calls `/health/ready` every five minutes
* request volume: `requests/count`
* response latency: `requests/duration`
* error rate: `requests/failed`, with result-code dimensions available for diagnosis

The Bicep deployment creates these enabled alerts:

* severity 1 availability alert when at least two test locations fail
* severity 2 server-error alert when at least one HTTP 5xx response occurs in five minutes
* severity 3 latency alert when average backend latency exceeds five seconds over 15 minutes

All alerts use the `ag-prepwise-prod-operations` Action Group. Its operator email is passed only at
deployment time and is not stored in the repository.

## Useful Log Analytics queries

Request rate, latency and failures:

```kusto
AppRequests
| where TimeGenerated > ago(1h)
| summarize Requests = sum(ItemCount),
            AverageDurationMs = avg(DurationMs),
            Failures = sumif(ItemCount, Success == false)
  by bin(TimeGenerated, 5m)
| order by TimeGenerated asc
```

Database dependency activity:

```kusto
AppDependencies
| where TimeGenerated > ago(1h)
| where DependencyType has "SQL" or Target has "postgres"
| project TimeGenerated, Name, Target, DurationMs, Success, OperationId
| order by TimeGenerated desc
```

Failed requests and their dependencies can be connected through `OperationId`:

```kusto
let failedOperations = AppRequests
| where TimeGenerated > ago(1h) and Success == false
| project OperationId;
AppDependencies
| where OperationId in (failedOperations)
| project TimeGenerated, OperationId, Name, Target, DurationMs, Success
```
