# Ivan - Roadmap

Last updated: 2025-11-27

## Architecture

Ivan uses the [llm-api-server](https://github.com/assareh/llm-api-server) library for core infrastructure.

- **ivan.py** (~80 lines) - Thin wrapper using `LLMServer`
- **tools.py** (~310 lines) - Customer notes tools + RAG initialization
- **config.py** (~70 lines) - Configuration extending `ServerConfig`
- **llm-api-server** (external) - RAG, web search, crawling, tool infrastructure

## Upcoming Tasks

### Medium Priority

1. **Terraform MCP Server Integration**
   - Add Terraform MCP server for enhanced Terraform tooling
   - Enable plan/apply operations, state inspection, and resource management
   - Reference: https://github.com/hashicorp/terraform-mcp-server

2. **Extended Documentation Sources**
   - Add HCP changelog indexing (`cloud.hashicorp.com/changelog`)
   - Add GitHub releases integration

### Lower Priority

3. **Remote Inference on EC2**
   - Deploy inference backend on AWS EC2 GPU instances
   - Enable remote model serving for improved performance
   - Support for larger models not feasible on local hardware

4. **Enhanced Metadata**
   - Extract version info from URLs
   - Classify doc_type (howto, concept, api, release-notes)
   - Add HCP boolean flag

5. **Browser Extension Improvements**
   - Restrict `matches` to Salesforce domains only
   - Better error handling for API responses

## Commands

```bash
# Run Ivan
uv run python ivan.py                    # Default settings
uv run python ivan.py --backend ollama   # Use Ollama
uv run python ivan.py --no-webui         # Skip Web UI

# Run certification tests
uv run python tests/test_certification.py --reasoning-effort medium
```

## Resources

- Main files: `ivan.py`, `tools.py`, `config.py`
- Test suite: `tests/test_certification.py`
- Core library: `llm-api-server` (external package)
- Documentation: `CLAUDE.md`, `README.md`
