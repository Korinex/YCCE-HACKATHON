# PS-06 Privacy Shield

## Overview
This project is a privacy-preserving document redaction service for Indian identity and financial data. It accepts text, image, and PDF inputs, identifies sensitive fields, and produces safe redacted output while keeping raw sensitive data in volatile server memory only.

## Repository context
- Server: FastAPI backend with secure session handling and schema contracts
- Client: Next.js shell for UI flow
- Integration: end-to-end test and demo placeholders
- Docs: contract and demo guidance

## Current working branch
- feat/backend-core

## Scope
Backend-1 owns the safe contracts, volatile session cache, request lifecycle, and privacy-safe backend skeleton for the pipeline seams.
