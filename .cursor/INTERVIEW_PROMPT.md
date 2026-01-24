# Interview Prompt Reference

> This document contains the original interview prompt for easy reference during development.

---

## PS Solutions Architect / AI Engineer Take Home

This exercise evaluates your ability to design and build production-grade AI agent systems. We're evaluating how you approach infrastructure challenges, implement robust agent systems with evaluation frameworks, and communicate technical decisions to both technical and non-technical stakeholders.

---

## Scenario

You are a Professional Services Architect/Engineer working with "InnovateCorp," an enterprise client preparing to deploy LangSmith Platform (self-hosted) and build AI agent systems to automate critical business workflows. The engagement has two main components:

**Part 1: Infrastructure Architecture** - Design the LangSmith Platform (self-hosted) deployment architecture

**Part 2: Agent Development** - Build and evaluate production-ready AI agents

**Note**: You can allocate more time to the part that aligns with your strengths, but both parts should be presented.

---

## Part 1: LangSmith Platform Architecture & Design

Design and document a **conceptual** architecture for deploying LangSmith Platform (self-hosted) to support InnovateCorp's agent operations.

Your architecture should demonstrate your understanding of the LangSmith Platform's core components. Refer to the [LangSmith self-hosted documentation](https://docs.langchain.com/langsmith/self-hosted) to identify the key services and components that make up a self-hosted LangSmith Platform installation.

Identify the required storage services and explain which ones can or should be externalized for production scaling purposes. Document your deployment architecture showing how LangSmith Platform components would be deployed, including component placement and resource considerations.

Explain your approach to scaling LangSmith Platform components and any other considerations you've identified. You can define the specific requirements and constraints based on your design choices.

InnovateCorp has existing Kubernetes infrastructure. You can choose any cloud provider and region that best fits your design.

**Note**: Focus on conceptual architecture and understanding of LangSmith Platform (self-hosted) components. No Infrastructure as Code scripts are required, just high-level architectural diagrams and documentation.

---

## Part 2: Agent Development & Evaluation

Build and evaluate an AI agent system for a domain of your choice. Examples include customer support automation, content generation, data processing workflows, or any other domain that demonstrates multi-agent capabilities. Clearly specify your chosen domain and the problem you're solving.

Your agent system should implement a multi-agent architecture with specialized agents for different workflow stages, using LangChain and LangGraph. Integrate with external APIs or data sources as needed for your domain. Your system must include a human-in-the-loop component that allows for human intervention, review, or approval at appropriate points in the workflow.

Create a comprehensive evaluation plan with a test dataset covering diverse scenarios. Use LangSmith to run evaluations, track agent traces, and measure performance metrics. Define custom evaluation metrics relevant to your domain and implement them using LangSmith's evaluation capabilities.

**Note**: Use LangChain/LangGraph for implementation and LangSmith for evaluation and observability. You can create a free LangSmith account at https://smith.langchain.com/

---

## Communication and Presentation

Prepare a 40-minute presentation for InnovateCorp's technical and business stakeholders.

For Part 1 (LangSmith Platform Architecture), provide a technical explanation covering LangSmith Platform component architecture, external service dependencies, and your scalability approach.

For Part 2 (Agent Development), provide a technical explanation of your agent architecture, design choices, trade-offs, evaluation results, and challenges you addressed. Translate your technical findings into business value, explaining how your solution improves KPIs.

Finally, identify and document any challenges or limitations you encountered with the frameworks and tools you used, highlighting areas for improvement in LangChain/LangGraph/LangSmith and any missing features (friction log).

---

## What to Submit

1. Submit **architecture documentation** including diagrams that show LangSmith Platform components, external services, deployment architecture, and scalability design.
2. Submit a well-organized **code repository** containing your multi-agent system implementation, evaluation framework, and test datasets.
3. Provide a **short demo** recording (5-10 minutes) demonstrating your agent system in action, key features, and LangSmith traces/evaluation results.
4. Submit a **presentation** deck covering the LangSmith Platform architecture overview, technical explanation for both parts, evaluation results, business impact, and product feedback.

---

## Checklist (Our Implementation)

### Part 1: LangSmith Platform Architecture
- [x] Conceptual architecture documented
- [x] Core components identified (Frontend, Backend, Platform Backend, Queue, Playground, ACE)
- [x] Storage services identified (PostgreSQL, Redis, ClickHouse, Blob Storage)
- [x] Externalization strategy (RDS, ElastiCache, S3, bundled ClickHouse)
- [x] AWS EKS deployment architecture
- [x] Resource sizing (POC vs Production)
- [x] Scaling approach documented

### Part 2: Agent Development
- [x] Domain specified: Vanpool misuse detection (Pool Patrol)
- [x] Multi-agent architecture: 3 agents (Location Validator, Shift Validator, Communications)
- [ ] LangChain tools implemented
- [ ] LangGraph workflow implemented
- [x] Human-in-the-loop: 2 points (unknown bucket review, pre-cancel approval)
- [ ] Test dataset created (40+ scenarios)
- [ ] Custom evaluation metrics implemented
- [ ] LangSmith integration for traces

### Deliverables
- [x] Architecture documentation (`docs/TECHNICAL_DESIGN.md`)
- [ ] Code repository (in progress)
- [ ] Demo recording (5-10 min)
- [ ] Presentation deck (user will create)
