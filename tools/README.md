# Tools

## court_rss_watcher.py

RSS-poller för Göteborgs tingsrätt från domstol.se.

### Installation

```bash
pip install -r ../requirements-dev.txt
```

### Användning

```bash
python3 tools/court_rss_watcher.py
```

### Testning

```bash
pytest tests/test_court_rss_watcher.py -v
```

### Funktioner

- Hämtar RSS från domstol.se (Göteborgs tingsrätt)
- Parsar RSS 2.0 + Atom namespace a10:content
- Unescape:ar HTML-entities i content
- Sparar senaste guid i `.state/gbg_tingsratt_last_guid.txt`
- Visar endast nya poster sedan senaste körning
