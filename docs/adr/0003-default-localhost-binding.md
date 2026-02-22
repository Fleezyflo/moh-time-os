# ADR-0003: Default to localhost Binding

## Status
Accepted

## Context
The dev server was hardcoded to bind `0.0.0.0`, exposing it on all network interfaces even during local development.

## Decision
Default `HOST` to `127.0.0.1` (localhost). Production sets `HOST=0.0.0.0` via environment variable.

## Consequences
- Dev server no longer exposed on LAN by default
- Production unchanged (explicit env var)
