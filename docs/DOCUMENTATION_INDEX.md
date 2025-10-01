# Documentation Index

This document provides an index of all documentation for the FuturesTradingLog application. The index is automatically generated using the Dataview plugin.

## All Documents

```dataview
TABLE WITHOUT ID
file.link as "File",
file.mtime as "Last Modified"
FROM "docs"
WHERE file.name != "DOCUMENTATION_INDEX.md"
SORT file.mtime DESC
```

## By Category

### Architecture

```dataview
TABLE WITHOUT ID
file.link as "File",
file.mtime as "Last Modified"
FROM "docs"
WHERE contains(file.tags, "architecture")
SORT file.mtime DESC
```

### Deployment

```dataview
TABLE WITHOUT ID
file.link as "File",
file.mtime as "Last Modified"
FROM "docs"
WHERE contains(file.tags, "deployment")
SORT file.mtime DESC
```

### Features

```dataview
TABLE WITHOUT ID
file.link as "File",
file.mtime as "Last Modified"
FROM "docs"
WHERE contains(file.tags, "feature")
SORT file.mtime DESC
```

### AI Collaboration
- **[AI_COLLABORATION.md](AI_COLLABORATION.md)** - A comprehensive guide for AI collaboration on the project.
