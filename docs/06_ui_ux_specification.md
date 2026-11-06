# UI / UX Specification

## Design Philosophy

The application must emphasize transparency.

Every generation action must display:

- Estimated Cost
- Estimated Time
- Estimated Storage
- Estimated GPU Usage
- Quality Expectations

before generation is allowed.

Users should never be surprised by cost or duration.

---

# Routes

## /

Landing Page

Purpose:

Marketing page.

Actions:

- Create Project
- View Demo
- Learn More

---

## /dashboard

Purpose:

Project Management

Components:

- Recent Projects
- Create Project Button
- Active Jobs
- Generation History

Table:

| Project | Status | Estimate | Created |
|----------|----------|----------|----------|

---

## /projects/new

Purpose:

Project Creation

Form Fields:

Video Idea
Target Length
Maximum Budget
Maximum Wait Time

Example:

Prompt:
"A retired astronaut discovers an underwater civilization."

Target Length:
5 minutes

Budget:
$5

Maximum Wait:
20 minutes

Buttons:

Analyze Project

---

## /projects/{projectId}/analysis

Purpose:

Planning Stage

Display:

Story Summary

Character Count

Scene Count

Complexity Rating

Storage Estimate

Generation Estimates

Cards:

Economy

Balanced

Premium

Each card displays:

Estimated Cost
Estimated Time
Resolution
Quality Score

Actions:

Select Plan

Edit Story

---

## /projects/{projectId}/story

Purpose:

Story Editing

Sections:

Title

Summary

Characters

Scenes

Editable Text Areas

Actions:

Save

Regenerate Story

Continue

---

## /projects/{projectId}/characters

Purpose:

Character Bible

Display:

Character Cards

Properties:

Name
Description
Reference Image

Actions:

Generate Portrait

Regenerate Portrait

Approve Character

---

## /projects/{projectId}/scenes

Purpose:

Scene Management

Display:

Scene Cards

Card Elements:

Scene Number

Description

Generated Image

Status

Actions:

Generate Image

Regenerate Image

Approve Scene

---

## /projects/{projectId}/generate

Purpose:

Generation Monitoring

Display:

Pipeline Progress

Stages:

Story

Characters

Images

Video

Export

Progress Bars:

Story
Images
Video

Estimated Remaining Time

Current Resource Usage

Current Cost Accumulated

---

## /projects/{projectId}/video

Purpose:

Final Output

Display:

Video Player

Metrics:

Final Cost

Generation Duration

Total Images

Video Length

Actions:

Download MP4

Create New Version

Return to Dashboard

---

# MVP Navigation Flow

Dashboard

↓

Create Project

↓

Analysis

↓

Story Review

↓

Character Review

↓

Scene Review

↓

Generate

↓

Download