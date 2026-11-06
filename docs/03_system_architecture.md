# System Architecture

## High-Level Architecture

User
↓
Frontend (Next.js)
↓
FastAPI Backend
↓
Project Services
↓
Generation Workers
↓
Storage
↓
Final MP4

## Frontend

Technology:

- Next.js
- TypeScript
- TailwindCSS

Responsibilities:

- Project management
- Cost display
- Progress tracking
- Scene review
- Download interface

## Backend

Technology:

- FastAPI
- Python

Responsibilities:

- Story generation
- Project orchestration
- Estimation engine
- Job status tracking

## Storage

Initial MVP:

Local filesystem

Future:

Cloudflare R2

## Database

Initial MVP:

SQLite

Future:

PostgreSQL

## Job Processing

Initial MVP:

FastAPI Background Tasks

Future:

Redis + Celery

## Generation Components

### Story Generator

Input:

Prompt

Output:

Story Bible

### Estimation Engine

Input:

Story Metadata

Output:

Cost/Time Estimates

### Image Generator

Input:

Scene Descriptions

Output:

Scene Images

### Video Composer

Input:

Scene Images

Output:

MP4 Video

Technology:

FFmpeg