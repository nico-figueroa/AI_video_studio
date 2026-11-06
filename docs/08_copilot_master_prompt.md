# GitHub Copilot Agent Master Prompt

You are building the initial MVP of AI Video Studio.

Read all files under /docs before implementation.

Follow the specifications exactly.

---

# Mission

Create a working end-to-end AI video generation prototype emphasizing transparency, predictability, and ethical resource consumption.

The platform must prioritize:

1. Cost visibility
2. Time visibility
3. Human review
4. Modularity
5. Future scalability

---

# Repository

AI_video_studio

---

# Technology Stack

Frontend

- Next.js
- TypeScript
- Tailwind CSS
- App Router

Backend

- FastAPI
- Pydantic
- SQLAlchemy

Database

- SQLite

Video

- FFmpeg

Image Generation

Provide an abstraction layer.

Initial implementation may use placeholder images or mock services.

The architecture must support future FLUX integration.

---

# Required Folder Structure

AI_video_studio

/frontend

/app
/components
/services

/backend

/api
/models
/schemas
/services
/repositories

/database

/workers

/docs

/tests

/scripts

---

# Backend Requirements

Implement:

Projects API

Story API

Character API

Scene API

Video API

Metrics API

Health Check API

Use service-oriented architecture.

Controllers must remain thin.

Business logic belongs in services.

Persistence belongs in repositories.

---

# Frontend Requirements

Implement routes from:

docs/06_ui_ux_specification.md

Implement responsive layouts.

Use reusable components.

Provide loading states.

Provide progress indicators.

Provide error handling.

---

# MVP Workflow

Create Project

↓

Analyze Project

↓

Generate Story Bible

↓

Present Estimates

↓

Select Plan

↓

Generate Placeholder Scene Images

↓

Generate Video

↓

Download Video

---

# Architecture Constraints

No hardcoded business logic inside UI components.

No direct database access from routes.

All backend endpoints must have request and response schemas.

All services should support future replacement of generation providers.

Use dependency injection patterns where practical.

---

# Non-Functional Requirements

Type-safe frontend.

Typed API responses.

Modular architecture.

Readable code.

Production-grade project structure.

Copilot should generate the complete initial scaffold and all required files.

Prioritize maintainability over optimization.

The result should be runnable locally using:

Backend

uvicorn main:app --reload

Frontend

npm run dev

Generate all code necessary for the initial MVP scaffold.