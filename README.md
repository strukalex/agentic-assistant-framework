# 🧠 Personal AI Assistant System (PAIAS)

A local-first ecosystem for autonomous agents, designed for long-term memory and complex reasoning.

## Project Overview

PAIAS is a modular framework for building and running AI agents that can perform real work. Unlike standard chatbots that rely on ephemeral context, this system is architected for persistence and reliability. It combines deterministic workflow orchestration with the adaptive reasoning capabilities of Large Language Models (LLMs).

## Core Architecture

The system implements a **Composite UI** and **Hybrid Orchestration** strategy, leveraging best-in-class open-source tools to handle specific layers of the agent lifecycle:

*   🧠 **Agent Logic:** **Pydantic AI** provides type-safe, atomic reasoning capabilities.
*   ⚙️ **Orchestration:** **Windmill** handles durable, long-running workflows, while **LangGraph** manages complex cyclical reasoning loops.
*   💾 **Memory:** **PostgreSQL** with **pgvector** serves as the single source of truth for both relational data and semantic vector search.
*   🔌 **Integrations:** The **Model Context Protocol (MCP)** standardizes how agents connect to external tools (Filesystem, Google Drive, GitHub), preventing vendor lock-in.
*   👀 **User Interface:** A composite layer using **LibreChat** for streaming chat interactions and Windmill for real-time workflow visualization.
