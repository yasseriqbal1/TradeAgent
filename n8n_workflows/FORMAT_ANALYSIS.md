# n8n Workflow Format Analysis

## Working Sample Format (Verified)

```json
{
  "name": "Simple Test Workflow",
  "nodes": [
    {
      "parameters": { ... },
      "name": "Node Name",           // ✅ REQUIRED
      "type": "n8n-nodes-base.xxx",  // ✅ REQUIRED
      "typeVersion": 1,              // ✅ REQUIRED
      "position": [x, y]             // ✅ REQUIRED
      // NO "id" field!               // ❌ MUST NOT EXIST
      // NO "credentials" field here for simple nodes
    }
  ],
  "connections": { ... },
  "active": false                    // ✅ REQUIRED
  // NO "settings", "staticData", "tags", etc.
}
```

## Issues Found in Current Premarket Workflow

### ❌ Problem 1: Node IDs Still Present

- Line 82: `"id": "http-groq-ai"`
- Line 126: `"id": "code-format-email"`
- Line 158: `"id": "send-email"`

The working sample has **NO** `"id"` fields on any nodes.

### ❌ Problem 2: Missing "name" Field

- Line 82-83: Has `"id"` but the `"name"` field is missing or in wrong place

### ⚠️ Problem 3: Credentials Format (Needs Testing)

```json
"credentials": {
  "httpHeaderAuth": {
    "id": "1",
    "name": "Groq API"
  }
}
```

This MIGHT be okay, but need to test with simpler workflow first.

## Test Strategy

### Test 1: test_workflow_simple.json

- ✅ Schedule trigger
- ✅ Simple HTTP GET (no auth)
- ✅ Code node
- ✅ NO credentials
- **Purpose**: Verify basic structure works

### Test 2: test_workflow_with_headers.json

- ✅ Webhook trigger
- ✅ HTTP with custom headers
- ✅ HTTP POST with body parameters
- ✅ Code node with complex logic
- ✅ NO credentials (using httpbin for testing)
- **Purpose**: Verify HTTP header/body format works

### Test 3: After tests pass, fix main workflows

- Remove ALL `"id"` fields from nodes
- Ensure `"name"` field exists for every node
- Keep credentials format (test separately)
- Ensure `"active": false` at end
- Remove metadata (settings, tags, etc.)

## Correct Node Structure

```json
{
  "parameters": {
    // All node-specific config here
  },
  "name": "Node Display Name",        // ✅ REQUIRED - This is what shows in n8n
  "type": "n8n-nodes-base.nodeName",  // ✅ REQUIRED
  "typeVersion": 1,                   // ✅ REQUIRED (or 2, 4.1 etc)
  "position": [x, y],                 // ✅ REQUIRED
  "credentials": {                    // ⚠️ OPTIONAL - only if needed
    "credentialType": {
      "id": "1",
      "name": "Credential Name"
    }
  }
}
```

## Next Steps

1. Import test_workflow_simple.json → Should work immediately
2. Import test_workflow_with_headers.json → Should work if structure is correct
3. Once both pass, fix premarket_scan_workflow.json
4. Then fix validation_scan_workflow.json
