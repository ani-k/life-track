# Life Goal Canvas — API Contract v1

Base URL: `/api/v1`
Auth: Bearer JWT in `Authorization` header (all endpoints except `/auth/*`)

---

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account (email + password) |
| POST | `/auth/login` | Returns `access_token` (JWT, 30 min) + `refresh_token` (7 days) |
| POST | `/auth/refresh` | Exchange refresh token for new access token |
| POST | `/auth/logout` | Revoke refresh token |

---

## Spaces

| Method | Path | Description |
|--------|------|-------------|
| GET | `/spaces` | List all spaces for current user |
| POST | `/spaces` | Create a new space (canvas) |
| GET | `/spaces/{space_id}` | Get space metadata |
| PATCH | `/spaces/{space_id}` | Update name / description / viewport |
| DELETE | `/spaces/{space_id}` | Delete space + all nodes + edges (cascade) |
| GET | `/spaces/{space_id}/graph` | **Full graph payload** — nodes + edges for canvas load |

---

## Nodes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/spaces/{space_id}/nodes` | Create node |
| GET | `/spaces/{space_id}/nodes/{node_id}` | Get single node |
| PATCH | `/spaces/{space_id}/nodes/{node_id}` | Update node (PATCH semantics) |
| DELETE | `/spaces/{space_id}/nodes/{node_id}` | Delete node + connected edges |
| PATCH | `/spaces/{space_id}/nodes/{node_id}/position` | Update canvas position only (high-frequency drag) |
| PATCH | `/spaces/{space_id}/nodes/{node_id}/status` | Toggle status (checkbox) |

---

## Edges

| Method | Path | Description |
|--------|------|-------------|
| POST | `/spaces/{space_id}/edges` | Create edge between two nodes |
| PATCH | `/spaces/{space_id}/edges/{edge_id}` | Update label / style |
| DELETE | `/spaces/{space_id}/edges/{edge_id}` | Delete edge |

---

## AI

| Method | Path | Description |
|--------|------|-------------|
| POST | `/spaces/{space_id}/ai/decompose` | Decompose a node into sub-nodes (returns proposals, not persisted) |
| POST | `/spaces/{space_id}/ai/decompose/accept` | Accept decomposition — persists proposed nodes + edges |
| POST | `/spaces/{space_id}/ai/chat` | Send chat message; may return graph mutations |
| GET | `/spaces/{space_id}/ai/sessions` | List AI chat sessions for a space |
| GET | `/spaces/{space_id}/ai/sessions/{session_id}` | Get message history |

---

## Error responses

All errors follow RFC 7807 Problem Details:
```json
{
  "type": "https://lifetrack.app/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "title must not be empty",
  "instance": "/api/v1/spaces/abc/nodes"
}
```

---

## Key Design Decisions

1. **Position updates are a separate endpoint** (`PATCH /nodes/{id}/position`) because
   drag-end events fire frequently; this endpoint skips full validation and returns 204.

2. **Decompose is a two-step flow** (propose → accept) to keep AI suggestions non-destructive.
   Users review before committing to the graph.

3. **GraphResponse** includes full node + edge arrays to minimise round-trips on canvas load;
   subsequent updates use individual node/edge endpoints.

4. **JWT expiry is short (30 min)** with a sliding refresh token to balance security and UX.
   Refresh tokens are stored server-side (Redis) for revocation support.
