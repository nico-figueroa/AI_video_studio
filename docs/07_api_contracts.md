# API Contracts

Base URL

/api/v1

---

# Health Check

GET /health

Response

200

{
  "status": "ok"
}

---

# Projects

## Create Project

POST /projects

Request

{
  "prompt": "A retired astronaut discovers an underwater civilization.",
  "target_minutes": 5,
  "max_budget": 5.00,
  "max_wait_minutes": 20
}

Response

201

{
  "project_id": 1,
  "status": "created"
}

---

## Get Project

GET /projects/{projectId}

Response

200

{
  "id": 1,
  "title": "The Forgotten Ocean",
  "status": "analysis_complete"
}

---

## List Projects

GET /projects

Response

[
  {
    "id": 1,
    "title": "The Forgotten Ocean"
  }
]

---

# Planning

## Analyze Project

POST /projects/{projectId}/analyze

Purpose

Generate:

- Story Bible
- Character Bible
- Scene List
- Estimates

Response

{
  "analysis_status": "completed"
}

---

## Retrieve Estimates

GET /projects/{projectId}/estimates

Response

{
  "economy": {
    "cost": 0.75,
    "minutes": 5,
    "resolution": "720p"
  },
  "balanced": {
    "cost": 2.10,
    "minutes": 12,
    "resolution": "1080p"
  },
  "premium": {
    "cost": 4.60,
    "minutes": 25,
    "resolution": "1080p_enhanced"
  }
}

---

# Story

## Get Story

GET /projects/{projectId}/story

Response

{
  "title": "",
  "summary": "",
  "characters": [],
  "scenes": []
}

---

## Update Story

PUT /projects/{projectId}/story

Request

{
  "title": "",
  "summary": "",
  "characters": [],
  "scenes": []
}

Response

{
  "updated": true
}

---

# Characters

## List Characters

GET /projects/{projectId}/characters

Response

[
  {
    "id": 1,
    "name": "Maya"
  }
]

---

## Generate Character Portrait

POST /characters/{characterId}/portrait

Response

{
  "status": "queued"
}

---

# Scenes

## List Scenes

GET /projects/{projectId}/scenes

## Generate Scene

POST /scenes/{sceneId}/generate

Response

{
  "status": "queued"
}

---

## Regenerate Scene

POST /scenes/{sceneId}/regenerate

Response

{
  "status": "queued"
}

---

# Video

## Generate Video

POST /projects/{projectId}/video

Request

{
  "plan": "balanced"
}

Response

{
  "job_id": "video-job-001",
  "status": "running"
}

---

## Video Status

GET /jobs/{jobId}

Response

{
  "status": "running",
  "progress": 67,
  "current_stage": "scene_generation"
}

---

## Download Video

GET /projects/{projectId}/video

Response

{
  "url": "/storage/video.mp4"
}

---

# Metrics

## Cost Summary

GET /projects/{projectId}/metrics

Response

{
  "estimated_cost": 2.10,
  "actual_cost": 1.98,
  "estimated_time": 12,
  "actual_time": 10
}