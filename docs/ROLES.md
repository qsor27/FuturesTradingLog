# Development Team Roles

This document defines the roles and responsibilities for the multi-AI development workflow using Zen Server models and Claude Code.

## Team Structure

### 1. Local Model (via Zen-Server) - **Researcher**
**Model**: `local` (Llama 3.2 via custom endpoint)
**Primary Role**: Research and Analysis

**Responsibilities:**
- Codebase exploration and understanding
- Requirements analysis and clarification
- Technical research and documentation review
- Architecture analysis and recommendations
- Best practices research
- Problem investigation and root cause analysis
- Technology stack evaluation
- Performance analysis and optimization research

**Interaction Pattern:**
- Receives research requests from Claude Code
- Provides detailed analysis and findings
- Suggests implementation approaches
- Documents technical decisions and rationale
- **Collaborates with Gemini Flash**: Passes research results to Code Developer for analysis and refinement
- **Accepts feedback**: Refocuses research based on Gemini Flash requests for deeper investigation

### 2. Gemini Flash (via Zen-Server) - **Code Developer**
**Model**: `flash` (Gemini 2.5 Flash)
**Primary Role**: Code Generation and Development

**Responsibilities:**
- Code implementation based on research findings
- Algorithm development and optimization
- Feature implementation
- Bug fixes and patches
- Code refactoring
- Test code generation
- API development
- Database query optimization

**Interaction Pattern:**
- Receives implementation specifications from Local Model research
- **Analyzes research results**: Reviews and evaluates research findings for implementation feasibility
- **Requests deeper research**: Can ask Local Model to investigate specific areas in more detail
- Generates code solutions based on refined research
- Passes code to Claude Code for review and integration
- Iterates on code based on feedback

### 3. Claude Code - **Reviewer and Integrator**
**Model**: Claude Sonnet 4
**Primary Role**: Code Review, Integration, and Project Management

**Responsibilities:**
- Code review and quality assurance
- Integration of generated code into codebase
- Testing and validation
- Git operations and version control
- Project coordination and task management
- Final implementation and deployment
- User interaction and requirement gathering
- System architecture decisions

**Interaction Pattern:**
- Initiates research requests to Local Model
- Reviews code from Gemini Flash
- Provides feedback and integration guidance
- Manages the overall development workflow
- Interfaces with the user for requirements and updates

## Workflow Example

1. **User Request** → Claude Code receives requirement
2. **Research Phase** → Claude Code asks Local Model to research the requirement
3. **Initial Analysis** → Local Model provides technical analysis and recommendations
4. **Research Refinement** → Gemini Flash analyzes research results and requests deeper investigation on specific areas
5. **Focused Research** → Local Model provides refined analysis based on Gemini Flash feedback
6. **Development** → Gemini Flash implements solution based on refined research
7. **Review** → Claude Code reviews generated code for quality and integration
8. **Integration** → Claude Code integrates and tests the solution
9. **Delivery** → Claude Code delivers final implementation to user

## Communication Protocols

- **Research Requests**: Detailed context and specific questions for Local Model
- **Code Specifications**: Clear requirements and constraints for Gemini Flash
- **Review Feedback**: Constructive feedback on generated code with specific improvements
- **Status Updates**: Regular communication about progress and blockers

## Model Selection Guidelines

- Use **Local Model** for: Complex analysis, research tasks, architecture decisions
- Use **Gemini Flash** for: Fast code generation, implementation tasks, algorithm development
- Use **Claude Code** for: Final review, integration, testing, and user communication