# Constitution Guide: Best Practices for `constitution.md`

Based on the investigation of the GitHub Spec Kit and its Spec-Driven Development (SDD) methodology, here is a comprehensive report on the `constitution.md` file.

## Executive Summary

**Role:** The `constitution.md` file acts as the **"Architectural DNA"** and immutable "Source of Truth" for your project.
**Location:** Typically found in `.specify/memory/constitution.md`.
**Function:** It serves as a persistent set of non-negotiable rules that AI agents (like Copilot or Claude) must follow for *every* task. Unlike ephemeral prompt instructions, the constitution enforces consistency across all generated specs, plans, and code.[^1][^2]

***

## 1. What SHOULD Be in `constitution.md`

This file should contain high-level, static rules that apply to the *entire* lifecycle of the project. If a rule changes, the fundamental nature of the project changes.

### A. Non-Negotiable Technology Stack

Explicitly define the tools to prevent AI from hallucinating alternatives or using outdated libraries.

* **Language \& Runtime:** (e.g., "Use TypeScript 5.0+ with Node.js 20 LTS").[^3]
* **Frameworks:** (e.g., "Frontend must be React with Vite; Backend must be Hono").[^3]
* **Styling/UI:** (e.g., "Use Tailwind CSS; do not write custom CSS files").[^3]
* **Database/ORM:** (e.g., "Use PostgreSQL with Prisma").


### B. Architectural Principles (The "Articles")

GitHub Spec Kit templates often organize these as "Articles" to enforce discipline.[^4]

* **Simplicity Gate:** Rules to prevent over-engineering (e.g., "Code must be understandable by a junior dev; no premature optimization").[^2]
* **Modularity:** (e.g., "Every feature must start as a standalone library/component before integration").[^4]
* **Anti-Abstraction:** (e.g., "Prefer duplication over wrong abstraction," "Use the framework directly; do not create wrapper classes").[^2]


### C. Operational Standards

* **Testing Strategy:** Define strict thresholds (e.g., "Every feature must have >80% unit test coverage," "Integration tests are mandatory for API endpoints").[^3]
* **Code Quality:** (e.g., "Must pass existing ESLint and Prettier configs").
* **Accessibility:** (e.g., "All UI components must be WCAG 2.1 AA compliant").


### D. Governance \& Workflow

* **Checklist References:** Reminders for the AI to check specific "gates" during the planning phase (e.g., "Pre-Design Simplicity Check").[^2]

***

## 2. What Should NOT Be in `constitution.md`

Avoid cluttering this file with information that changes frequently or applies only to specific tasks.

* **Feature-Specific Requirements:** Do *not* describe specific user stories or features here (e.g., "The login button should be blue"). These belong in `spec.md` or `plan.md`.[^5]
* **Vague Instructions:** Avoid "fluff" like "Write good code" or "Be efficient." These are interpreted subjectively by AI. Use concrete constraints instead.[^6]
* **Ephemeral Context:** Do not include current sprint details, temporary bug fixes, or "todo" lists.
* **Contradictory Goals:** Avoid opposing instructions like "Optimize for maximum speed" AND "Optimize for minimal memory usage" without explaining the trade-off priority.[^6]
* **Tutorial Content:** Do not paste entire documentation pages (e.g., "How to use React"). The AI already knows this; just specify *which* version or pattern to use.

***

## 3. Best Practices \& Anti-Patterns

Use this table to audit your current `constitution.md`.


| **Anti-Pattern (Bad)** | **Why it Fails** | **Best Practice (Good)** |
| :-- | :-- | :-- |
| **"Write clean code"** | Too vague; AI models have different definitions of "clean." | "Use functional programming patterns; max function length 20 lines." [^6] |
| **"Never use libraries"** | Too restrictive; forces AI to reinvent the wheel. | "Use only approved libraries listed in `package.json`; for new needs, request approval." [^6] |
| **"Make it fast and small"** | Contradictory; confuses the optimization target. | "Prioritize runtime performance over bundle size." |
| **"Implement User Login"** | Scope creep; this is a *feature*, not a *principle*. | "All authentication must use OAuth 2.0 flow." (Principle) |


***

## 4. Assessment Checklist

To determine if your `constitution.md` aligns with best practices, ask these questions:

1. **Is it Immutable?** Could you build 10 different features for this project without changing this file? (If yes, it's good).
2. **Is it Enforceable?** Can a code reviewer (or AI) objectively say "Yes" or "No" to whether a rule was followed? (e.g., "Code coverage > 80%" is enforceable; "Good tests" is not).
3. **Is it Concise?** Does it avoid explaining *why* (tutorial style) and focus on *what* (rules)?
4. **Does it Gate the Plan?** Does the `plan-template.md` explicitly reference checks in this constitution? (e.g., "Did you check Article VII?").[^7]

### Recommended Structure

If generating a new file, your structure should look similar to this:

```markdown
# Project Constitution

## 1. Tech Stack (Non-Negotiable)
- Language: [Language]
- Framework: [Framework]

## 2. Architectural Principles
- Article I: Simplicity First
- Article II: Integration-First Development

## 3. Operational Standards
- Testing: [Coverage Rules]
- Styling: [Style Guide]

## 4. Amendment Process
- Principles can only be changed via PR with rationale.
```

<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30][^31][^32][^33][^34][^35][^36][^37][^38][^39][^40][^41][^42][^43][^44][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://www.epam.com/insights/ai/blogs/inside-spec-driven-development-what-githubspec-kit-makes-possible-for-ai-engineering

[^2]: https://github.com/github/spec-kit/blob/main/spec-driven.md

[^3]: https://virtuslab.com/blog/ai/spec-kit-tames-ai-coding-chaos/

[^4]: https://deepwiki.com/github/spec-kit/3.2-the-constitution-system

[^5]: https://github.com/github/spec-kit/issues/1149

[^6]: https://deepwiki.com/github/spec-kit/4.11-constitutional-governance-system

[^7]: https://github.com/github/spec-kit/blob/main/templates/plan-template.md

[^8]: https://github.com/github/spec-kit/issues/80

[^9]: https://github.com/github/spec-kit

[^10]: https://github.com/github/spec-kit/blob/main/memory/constitution.md

[^11]: https://developer.microsoft.com/blog/spec-driven-development-spec-kit

[^12]: https://www.youtube.com/watch?v=8xXV4FeaF9M

[^13]: https://azurewithaj.com/posts/github-spec-kit/

[^14]: https://codestandup.com/posts/2025/github-spec-kit-tutorial-constitution-command/

[^15]: https://blog.logrocket.com/github-spec-kit/

[^16]: https://ainativedev.io/news/a-look-at-spec-kit-githubs-spec-driven-software-development-toolkit

[^17]: https://blog.sshh.io/p/how-i-use-every-claude-code-feature

[^18]: https://github.com/github/spec-kit/issues/366

[^19]: https://www.youtube.com/watch?v=_PeYeRWeQWw

[^20]: https://apidog.com/blog/claude-md/

[^21]: https://github.com/github/spec-kit/issues/297

[^22]: https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/

[^23]: https://github.com/github/spec-kit/issues/372

[^24]: https://www.youtube.com/watch?v=xgnIBh25a5A

[^25]: https://github.com/Azure-Samples/azure-speckit-constitution

[^26]: https://github.com/github/spec-kit/discussions/773

[^27]: https://github.com/github/spec-kit/discussions/980

[^28]: https://github.com/github/spec-kit/issues/458

[^29]: https://www.youtube.com/watch?v=7tjmA_0pl2c

[^30]: https://www.reddit.com/r/ClaudeCode/comments/1nb8mi9/anyone_tried_githubs_speckit_with_claude_code/

[^31]: https://www.reddit.com/r/GithubCopilot/comments/1llss4p/this_is_my_generalinstructionsmd_file_to_use_with/

[^32]: https://github.com/github/spec-kit/issues/916

[^33]: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

[^34]: https://www.reddit.com/r/ChatGPTCoding/comments/1jl6gll/copilotinstructionsmd_has_helped_me_so_much/

[^35]: https://www.youtube.com/watch?v=a9eR1xsfvHg

[^36]: https://github.blog/ai-and-ml/generative-ai/spec-driven-development-using-markdown-as-a-programming-language-when-building-with-ai/

[^37]: https://den.dev/blog/github-spec-kit/

[^38]: https://robotpaper.ai/i-tried-out-github-spec-kit-and-all-i-got-was-this-not-terrible-website/

[^39]: https://github.com/github/spec-kit/issues

[^40]: https://github.com/github/spec-kit/discussions/152

[^41]: https://carlytaylor.substack.com/p/ai-spec-driven-development

[^42]: https://github.com/github/spec-kit/discussions/883

[^43]: https://www.linkedin.com/pulse/spec-driven-development-why-githubs-spec-kit-changes-how-shandrokha-g3omf

[^44]: https://www.reddit.com/r/GithubCopilot/comments/1o6iy7c/github_speckit_is_just_too_complex/

