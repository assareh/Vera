# Automatic Web Index Management

## What is it?

The HashiCorp web documentation index is now **fully automatic**. You don't need to think about it - it just works!

## How it works

### On Startup

When you run `python3 ivan.py`, the system:

1. **Checks index status** (< 1 second)
   - Does index exist?
   - Is it up to date? (checks age vs 7-day threshold)
   - Are there cached pages we can use?

2. **Shows status message**
   ```
   ============================================================
   HashiCorp Web Documentation Index Status
   ============================================================
   ✓ Index exists (last updated: 2.5 hours ago)
   ✓ Index is up to date
   ============================================================
   ```

3. **Launches background build if needed**
   - Spawns `build_web_index.py` as a detached subprocess
   - Logs to `build_index_<timestamp>.log`
   - Doesn't block Ivan from starting!

4. **Starts Ivan immediately**
   - You can start using Ivan right away
   - Index builds in background
   - Tools using the index will work once it's ready

### Background Updates

A background thread checks for updates **every 24 hours**:
- If index is older than 7 days → automatic rebuild
- Runs silently in background
- Non-disruptive to running queries

### Build Process

The build process is **resumable at every stage**:

| Stage | Saved To | Resume Behavior |
|-------|----------|-----------------|
| URL Discovery | `url_list.json` | Skip if exists |
| Page Scraping | `pages/*.json` | Skip cached pages |
| Chunking | `chunks.json` | Skip if exists |
| Embeddings | `index/` + progress file | Resume from last batch |

**If interrupted:** Just restart Ivan. It will resume automatically.

## Status Checking

### While Ivan is Running

Via CLI:
```bash
./index_status
```

Via API:
```bash
curl http://localhost:8000/index/status
```

Response:
```json
{
  "index_exists": true,
  "needs_build": false,
  "needs_update": false,
  "last_update": "2025-11-05T14:30:00",
  "age_hours": 2.5,
  "cached_pages": 5964,
  "chunks_ready": true,
  "build_in_progress": false
}
```

### When Ivan is NOT Running

```bash
python3 check_index_status.py
```

## Manual Control (Optional)

### Force Rebuild

```bash
# Delete cache
rm -rf hashicorp_web_docs/

# Restart Ivan - will rebuild automatically
python3 ivan.py
```

### Pre-build Before First Use

```bash
# Build manually first
./run_build_index.sh

# Then start Ivan (will use existing index)
python3 ivan.py
```

### Disable Automatic Updates

Edit `ivan.py` and modify the manager initialization:

```python
from web_index_manager import WebIndexManager

manager = WebIndexManager(
    update_interval_hours=168,  # 7 days
    auto_update=False  # Disable automatic updates
)
manager.initialize_on_startup()
```

## Architecture

### Components

1. **`web_index_manager.py`** - Orchestrates automatic builds
   - Checks index status
   - Spawns build subprocess
   - Monitors build progress
   - Schedules periodic updates

2. **`build_web_index.py`** - The build worker
   - Runs as a detached subprocess
   - Logs to timestamped file
   - Saves progress incrementally
   - Can be interrupted and resumed

3. **`hashicorp_web_search.py`** - Core indexing logic
   - Crawls web pages
   - Generates chunks
   - Creates FAISS embeddings
   - Manages cache files

### Process Lifecycle

```
ivan.py startup
    ↓
web_index_manager.initialize_on_startup()
    ↓
Check index status
    ↓
    ├─→ Index OK → Continue (start update checker)
    │
    └─→ Index needed → subprocess.Popen(build_web_index.py)
                           ↓
                       (detached process)
                           ↓
                       Logs to file
                           ↓
                       Saves progress
                           ↓
                       Completes or interrupted
                           ↓
                       (can resume on next startup)
```

### Background Update Checker

```
Threading loop (every 24 hours)
    ↓
Check if index is stale (> 7 days)
    ↓
    ├─→ Fresh → Sleep
    │
    └─→ Stale → Start build subprocess
```

## Troubleshooting

### "Index not building"

Check if build process is running:
```bash
ps aux | grep build_web_index
```

Check latest log:
```bash
tail -f build_index_*.log
```

### "Build process stuck"

The process saves progress every 10k chunks. If interrupted:
1. Kill the process: `kill <PID>`
2. Restart Ivan: `python3 ivan.py`
3. It will resume automatically

### "Want to see build progress"

Use the manual build script instead:
```bash
./run_build_index.sh
```

This shows progress in your terminal.

### "Build keeps restarting"

Check the update interval. If too short, it will keep rebuilding.

Default is 7 days (168 hours).

## Benefits

✅ **Zero Configuration** - Just works out of the box
✅ **Non-Blocking** - Ivan starts immediately
✅ **Automatic Updates** - Stays fresh without manual intervention
✅ **Resumable** - Interruptions don't lose progress
✅ **Background Operation** - Doesn't interfere with usage
✅ **Status Visibility** - Easy to check what's happening
✅ **Manual Override** - Can still build manually if desired

## Implementation Details

### Why Subprocess Instead of Thread?

- **Isolation**: Build process can crash without taking down Ivan
- **Resource control**: Can monitor/kill build independently
- **Logging**: Separate log files for each build
- **Resume**: Process can outlive Ivan shutdown

### Why Not Celery/RQ?

- **Simplicity**: No additional dependencies or infrastructure
- **Lightweight**: Just Python subprocess module
- **Sufficient**: Single-worker task, no distribution needed

### Future Enhancements

Potential improvements:
- [ ] Progress notifications via websocket
- [ ] Build status in Web UI
- [ ] Configurable update schedule
- [ ] Delta updates (only changed pages)
- [ ] Multi-machine distributed builds
