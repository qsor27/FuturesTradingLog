---
tags: api
---

# API Endpoint: {{tp.file.title}}

## 1. Endpoint

`GET /api/v2/`

## 2. Parameters

| Name | Type | Description |
|---|---|---|
| `id` | `integer` | The ID of the resource. |

## 3. Response

```json
{
  "id": 1,
  "name": "Resource Name"
}
```

## 4. Error Codes

| Code | Description |
|---|---|
| `404` | Resource not found. |
